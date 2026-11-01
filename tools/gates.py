#!/usr/bin/env python3
"""Every gate on the shipped test networks, in one run. Writes results/gates.json and gates.log.

  python3 tools/gates.py <build-dir>

<build-dir> comes from tools/build.sh and must hold kwswmm, stockseq, kwswmm-musl and
stockseq-musl. Needs node for the WebAssembly gate.
"""
import json, os, re, subprocess, sys, tempfile, hashlib, glob, datetime
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
B = os.path.abspath(sys.argv[1]); M = os.path.join(R, 'models'); TOOLS = os.path.join(R, 'tools')
models = sorted(glob.glob(os.path.join(M, '*.inp'))) + sorted(glob.glob(os.path.join(R, 'tests', 'fanout', '*.inp')))  # + the 65-outlet review networks
log = []; gates = []
def sh(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw); log.append('$ ' + ' '.join(cmd) + '\n' + p.stdout + p.stderr); return p
def routing(f):
    m = re.search(r'(?m)^FLOW_ROUTING\s+(\S+)', open(f).read()); return m.group(1).upper() if m else 'KINWAVE'

# 1. null effect: models with nothing to split or loop
TD = tempfile.mkdtemp(); tree = []
for f in models:
    sh([os.path.join(B, 'kwswmm'), f, os.path.join(TD, 'a.rpt'), os.path.join(TD, 'a.out')], env={'KWSPLIT': '1', 'KWLOOP': '1'})
    if 'KW/SF extension' not in open(os.path.join(TD, 'a.rpt'), encoding='latin-1').read(): tree.append(f)
p = sh(['bash', os.path.join(TOOLS, 'null_gate.sh'), B] + tree)
m = re.search(r'null gate: (\d+) runs, (\d+) differences', p.stdout)
gates.append(['Null effect: networks with nothing to split or loop, modes 0/0, 1/1, 2/1, 3/1 against stock',
              f'{m.group(1)} runs on {len(tree)} networks, {m.group(2)} differences (.out bytes, .rpt bar clock lines)', m.group(2) == '0'])

# 2. stock refusals preserved with the options off, and lifted with them on
rows = []; ok = True
for f in models:
    if routing(f) == 'DYNWAVE': continue
    for meth in ('KINWAVE', 'STEADY'):
        txt = re.sub(r'(?m)^FLOW_ROUTING\s+\S+', 'FLOW_ROUTING ' + meth, open(f).read()); fi = os.path.join(TD, 'r.inp'); open(fi, 'w').write(txt)
        res = {}
        for lab, exe, env in (('stock', 'stockseq', {}), ('off', 'kwswmm', {'KWSPLIT': '0', 'KWLOOP': '0'}), ('on', 'kwswmm', {'KWSPLIT': '1', 'KWLOOP': '1'})):
            sh([os.path.join(B, exe), fi, os.path.join(TD, 'r.rpt'), os.path.join(TD, 'r.out')], env=env)
            res[lab] = sorted(set(int(x) for x in re.findall(r'ERROR (\d+)', open(os.path.join(TD, 'r.rpt'), encoding='latin-1').read())))
        if res['stock']:
            rows.append(f"{os.path.basename(f)} {meth}: stock {res['stock']}, off {res['off']}, on {res['on'] or 'runs'}")
            ok = ok and res['off'] == res['stock'] and not res['on']
log.append('\n'.join(rows))
n133 = sum(1 for r in rows if '133' in r.split(',')[0]); n131 = sum(1 for r in rows if '131' in r.split(',')[0])
gates.append(['Stock refusals: options off reproduce stock\'s ERROR 133 / 131; options on run the network',
              f'{len(rows)} cases (ERROR 133: {n133}, ERROR 131: {n131}), KINWAVE and STEADY, all as expected' if ok else 'FAILED: see gates.log', ok])

# 3. order independence
split_loop = [f for f in models if f not in tree]
p = sh([sys.executable, os.path.join(TOOLS, 'order_check.py'), os.path.join(B, 'kwswmm')] + split_loop)
k = len(re.findall(r'identical to original: 3 of 3', p.stdout))
gates.append(['Order independence: [JUNCTIONS] and [CONDUITS] shuffled, 3 seeds, HEAD + loops',
              f'{k} of {len(split_loop)} networks: link peaks and continuity identical', k == len(split_loop)])

# 3b. outlet count and position: the boundary that kwmod.c v1 got wrong (char done[64])
def continuity_lines(rpt):
    t = open(rpt, encoding='latin-1').read(); i = t.find('Flow Routing Continuity')
    g = lambda k: float(re.search(k + r' \.+\s+(\S+)', t[i:]).group(1))
    return g('External Outflow'), g('Flooding Loss')
bad = []; nrun = 0; mxb = 0.0
for meth in ('STEADY', 'KINWAVE'):
    for n in (63, 64, 65, 66, 130):
        for s in ('1', '2', '3'):
            outs = {}
            for pos in sorted(set(p for p in (1, 64, 65, n) if p <= n)):
                fi = os.path.join(TD, 'mo.inp')
                sh([sys.executable, os.path.join(TOOLS, 'many_outlets.py'), str(n), str(pos), fi, '--routing', meth])
                p = sh([os.path.join(B, 'kwswmm'), fi, os.path.join(TD, 'mo.rpt'), os.path.join(TD, 'mo.out')], env={'KWSPLIT': s, 'KWLOOP': '1'})
                imb = float(re.search(r'maxImb=(\S+)', p.stdout).group(1)); out, flood = continuity_lines(os.path.join(TD, 'mo.rpt'))
                nrun += 1; mxb = max(mxb, imb); outs[pos] = out
                if imb >= 1e-9 or flood != 0.0: bad.append(f'{meth} n={n} rule {s} limited outlet {pos}: gap {imb:.3g} cfs, flooding {flood}')
            if len(set(outs.values())) != 1: bad.append(f'{meth} n={n} rule {s}: outflow volume depends on position {outs}')
log.append('outlet-count gate:\n' + ('\n'.join(bad) or 'no failures'))
gates.append(['Outlet count and position: one junction with 63, 64, 65, 66 and 130 outlets, a 0.1 cfs-limited outlet first, 64th, 65th and last, three rules, KINWAVE and STEADY',
              f'{nrun} runs: largest allocation gap {mxb:.2g} cfs, no flooding, outflow volume the same wherever the limited outlet sits' if not bad else f'FAILED in {len(bad)} cases: see gates.log',
              not bad])

# 3c. fan-out, as the second review built it: names fixed, the capped outlet moved through the list (tools/fanout_check.py)
p = sh([sys.executable, os.path.join(TOOLS, 'fanout_check.py'), os.path.join(B, 'kwswmm')])
m = re.search(r'fan-out gate: (\d+) runs, (\d+) failures, largest allocation gap (\S+) cfs, largest change in any outlet peak with the capped outlet moved (\S+) cfs', p.stdout)
gates.append(['Fan-out: 64, 65, 66 and 130 outlets from one junction, one capped by a flow limit and moved through the list, three rules, KINWAVE and STEADY',
              f'{m.group(1)} runs, {m.group(2)} failures: largest allocation gap {float(m.group(3)):.2g} cfs, no flooding, outlet peaks unchanged by position (largest change {float(m.group(4)):.2g} cfs)', m.group(2) == '0'])

# 4. conservation
mx = 0.0
for f in split_loop:
    for s in ('1', '2', '3'):
        p = sh([os.path.join(B, 'kwswmm'), f, os.path.join(TD, 'c.rpt'), os.path.join(TD, 'c.out')], env={'KWSPLIT': s, 'KWLOOP': '1'})
        m = re.search(r'maxImb=(\S+)', p.stdout); mx = max(mx, float(m.group(1)))
gates.append(['Conservation: largest gap between flow allocated and flow available at any split junction, any step, three rules',
              f'{mx:.2g} cfs over {len(split_loop) * 3} runs', mx < 1e-9])

# 5. WebAssembly against native musl
p = sh(['node', os.path.join(TOOLS, 'wasm_check.js'), B] + models)
a = re.search(r'swmm524kw.wasm vs native musl: (\d+)/(\d+)', p.stdout); b = re.search(r'swmm524.wasm \(stock\) vs native musl: (\d+)/(\d+)', p.stdout)
gates.append(['WebAssembly: swmm524kw.wasm against a native musl build, every network, every mode',
              f'{a.group(1)} of {a.group(2)} .out files byte-identical', a.group(1) == a.group(2)])
gates.append(['WebAssembly: swmm524.wasm (stock) against native musl stock',
              f'{b.group(1)} of {b.group(2)} .out files byte-identical', b.group(1) == b.group(2)])

# 6. wasm reproducible, patch reproduces the source
for w in ('swmm524kw.wasm', 'swmm524.wasm'):
    if os.path.exists(os.path.join(B, w)):
        same = open(os.path.join(B, w), 'rb').read() == open(os.path.join(R, 'wasm', w), 'rb').read()
        gates.append([f'Reproducible build: {w} rebuilt by tools/build.sh', 'byte-identical to wasm/' + w if same else 'DIFFERS', same])
p = sh(['bash', os.path.join(TOOLS, 'check_patch.sh')])
gates.append(['Patch: patch/swmm524-kw.patch on pristine EPA v5.2.4 reproduces src/', p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'not run', p.returncode == 0])

for g in gates: print(('PASS ' if g[2] else 'FAIL ') + g[0] + ': ' + g[1])
sha = lambda f: hashlib.sha256(open(f, 'rb').read()).hexdigest()
json.dump(dict(date=datetime.date.today().isoformat(), build=B, gates=gates,
               engines=[[os.path.basename(f), os.path.getsize(f), sha(f)] for f in sorted(glob.glob(os.path.join(B, '*'))) if os.path.isfile(f)]),
          open(os.path.join(R, 'results', 'gates.json'), 'w'), indent=1)
open(os.path.join(R, 'results', 'gates.log'), 'w').write('\n'.join(log))
sys.exit(0 if all(g[2] for g in gates) else 1)
