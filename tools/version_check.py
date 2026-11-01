#!/usr/bin/env python3
"""What changed between two engine versions, on every forked network the corpus has.

  python3 tools/version_check.py <build-dir> <corpus-dir> results/gate_whatif.jsonl results/version_check.json [old-rev]

Builds the engine from git revision old-rev (default 5c6c060, kw v1) and runs every corpus network
that stock 5.2.4 refuses under KINWAVE and swmm5-kw routes (from the what-if records) through
that old engine and through <build-dir>/kwswmm, with HEAD, CAPACITY and AREA (loops on), routing
switched to KINWAVE exactly as tools/corpus_gate.py --force-routing does. Records each run's
largest allocation gap (swmm_getKwStats v[3]), routing continuity, and whether the two .out files
are byte-identical. The claim to check for v1.1: output changes only where a v1 defect fired.
"""
import json, os, re, subprocess, sys, tempfile, hashlib
from concurrent.futures import ThreadPoolExecutor
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
B, C, REC, OUT = [os.path.abspath(x) for x in sys.argv[1:5]]
REV = sys.argv[5] if len(sys.argv) > 5 else '5c6c060'

T = tempfile.mkdtemp()
subprocess.run(f'git -C "{R}" archive {REV} src | tar -x -C "{T}"', shell=True, check=True)
S = os.path.join(T, 'src', 'solver'); OLD = os.path.join(T, 'kwold')
os.makedirs(os.path.join(T, 'tools')); open(os.path.join(T, 'tools', 'kwmain.c'), 'w').write(open(os.path.join(R, 'tools', 'kwmain.c')).read())  # the driver came after v1; its API did not change
subprocess.run(['gcc', '-O2', '-D_FORTIFY_SOURCE=0', '-U_FORTIFY_SOURCE', '-w', '-I' + S, '-I' + os.path.join(S, 'include')]
               + [os.path.join(S, f) for f in sorted(os.listdir(S)) if f.endswith('.c')]
               + [os.path.join(T, 'tools', 'kwmain.c'), '-lm', '-o', OLD], check=True)
NEW = os.path.join(B, 'kwswmm')

def force_copy(inp):
    t = open(inp, encoding='latin-1').read()
    if re.search(r'(?mi)^\s*FLOW_ROUTING\s', t): t = re.sub(r'(?mi)^(\s*FLOW_ROUTING\s+)\S+', r'\g<1>KINWAVE', t)
    else: t = re.sub(r'(?mi)^\[OPTIONS\]\s*$', '[OPTIONS]\nFLOW_ROUTING         KINWAVE', t, count=1)
    fd, p = tempfile.mkstemp(prefix='.kwver_', suffix='.inp', dir=os.path.dirname(inp)); os.close(fd)
    open(p, 'w', encoding='latin-1').write(t); return p

def run(exe, inp, mode):
    d = tempfile.mkdtemp(); rpt, out = os.path.join(d, 'm.rpt'), os.path.join(d, 'm.out')
    p = subprocess.run([exe, inp, rpt, out], env={'KWSPLIT': mode, 'KWLOOP': '1'}, cwd=os.path.dirname(inp),
                       capture_output=True, text=True, timeout=900)
    m = re.search(r'maxImb=(\S+)', p.stdout)
    h = hashlib.sha256(open(out, 'rb').read()).hexdigest() if os.path.exists(out) else ''
    r = open(rpt, encoding='latin-1').read() if os.path.exists(rpt) else ''
    c = re.search(r'Flow Routing Continuity.*?Continuity Error \(%\) \.+\s+(\S+)', r, re.S)
    subprocess.run(['rm', '-rf', d])
    return dict(imb=float(m.group(1)) if m else None, sha=h, cont=c.group(1) if c else None)

def one(r):
    src = os.path.join(C, r['inp']); cp = force_copy(src); row = dict(inp=r['inp'])
    try:
        for mode in ('1', '2', '3'):
            a, b = run(OLD, cp, mode), run(NEW, cp, mode)
            row['m' + mode] = dict(imb_old=a['imb'], imb_new=b['imb'], out_same=a['sha'] == b['sha'] and a['sha'] != '',
                                   cont_old=a['cont'], cont_new=b['cont'])
    finally:
        os.remove(cp)
    return row

recs = [json.loads(l) for l in open(REC)]
todo = [r for r in recs if r['census'] and r.get('m11', {}).get('rc') == 0 and not r['m11'].get('errors')]
with ThreadPoolExecutor(2) as px: rows = list(px.map(one, todo))
summary = dict(old=REV, networks=len(rows))
for mode, name in (('1', 'HEAD'), ('2', 'CAPACITY'), ('3', 'AREA')):
    ch = [x for x in rows if not x['m' + mode]['out_same']]
    summary[name] = dict(changed=len(ch),
                         changed_and_old_gap_closed=sum(1 for x in ch if (x['m' + mode]['imb_new'] or 0) < (x['m' + mode]['imb_old'] or 0)),
                         max_gap_old=max((x['m' + mode]['imb_old'] or 0) for x in rows),
                         max_gap_new=max((x['m' + mode]['imb_new'] or 0) for x in rows))
json.dump(dict(summary=summary, rows=rows), open(OUT, 'w'), indent=1)
print(json.dumps(summary, indent=1))
for mode in ('1', '2', '3'):
    for x in rows:
        if not x['m' + mode]['out_same']:
            y = x['m' + mode]; print(f"  rule {mode} changed: {x['inp'][:52]:52s} gap {y['imb_old']:.2e} -> {y['imb_new']:.2e}  cont {y['cont_old']} -> {y['cont_new']}")
