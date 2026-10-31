#!/usr/bin/env python3
"""Evidence for patch/kw-v1.1-head-overshoot.patch (proposed, not applied).

  python3 tools/head_fix_check.py <build-dir> <corpus-dir> results/gate_whatif.jsonl results/head_fix_check.json

Builds the engine with the patch applied, then runs every corpus network that stock 5.2.4
refuses under KINWAVE and swmm5-kw routes (from the what-if records) through both the engine as
it stands (<build-dir>/kwswmm) and the patched one, HEAD + loops, routing switched to KINWAVE
exactly as tools/corpus_gate.py --force-routing does. Records each engine's largest allocation
imbalance (swmm_getKwStats v[3]) and whether the two .out files are identical.
The claim to check: the fix changes output only where the defect fired, and closes it there.
"""
import json, os, re, subprocess, sys, tempfile, hashlib
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
B, C, REC, OUT = [os.path.abspath(x) for x in sys.argv[1:5]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

T = tempfile.mkdtemp(); subprocess.run(['cp', '-r', os.path.join(R, 'src'), T], check=True)
subprocess.run(['patch', '-p1', '--quiet', '-i', os.path.join(R, 'patch', 'kw-v1.1-head-overshoot.patch')], cwd=T, check=True)
S = os.path.join(T, 'src', 'solver'); FIX = os.path.join(T, 'kwfix')
subprocess.run(['gcc', '-O2', '-D_FORTIFY_SOURCE=0', '-U_FORTIFY_SOURCE', '-w', '-I' + S, '-I' + os.path.join(S, 'include')]
               + [os.path.join(S, f) for f in sorted(os.listdir(S)) if f.endswith('.c')]
               + [os.path.join(R, 'tools', 'kwmain.c'), '-lm', '-o', FIX], check=True)
CUR = os.path.join(B, 'kwswmm')

def force_copy(inp):
    t = open(inp, encoding='latin-1').read()
    if re.search(r'(?mi)^\s*FLOW_ROUTING\s', t): t = re.sub(r'(?mi)^(\s*FLOW_ROUTING\s+)\S+', r'\g<1>KINWAVE', t)
    else: t = re.sub(r'(?mi)^\[OPTIONS\]\s*$', '[OPTIONS]\nFLOW_ROUTING         KINWAVE', t, count=1)
    fd, p = tempfile.mkstemp(prefix='.kwfix_', suffix='.inp', dir=os.path.dirname(inp)); os.close(fd)
    open(p, 'w', encoding='latin-1').write(t); return p

def run(exe, inp):
    d = tempfile.mkdtemp(); rpt, out = os.path.join(d, 'm.rpt'), os.path.join(d, 'm.out')
    p = subprocess.run([exe, inp, rpt, out], env={'KWSPLIT': '1', 'KWLOOP': '1'}, cwd=os.path.dirname(inp),
                       capture_output=True, text=True, timeout=600)
    m = re.search(r'maxImb=(\S+)', p.stdout)
    h = hashlib.sha256(open(out, 'rb').read()).hexdigest() if os.path.exists(out) else ''
    r = open(rpt, encoding='latin-1').read() if os.path.exists(rpt) else ''
    c = re.search(r'Flow Routing Continuity.*?Continuity Error \(%\) \.+\s+(\S+)', r, re.S)
    subprocess.run(['rm', '-rf', d])
    return dict(imb=float(m.group(1)) if m else None, sha=h, cont=c.group(1) if c else None)

recs = [json.loads(l) for l in open(REC)]
todo = [r for r in recs if r['census'] and r.get('m11', {}).get('rc') == 0 and not r['m11'].get('errors')]
rows = []
for r in todo:
    src = os.path.join(C, r['inp']); cp = force_copy(src)
    try:
        a, b = run(CUR, cp), run(FIX, cp)
    finally:
        os.remove(cp)
    rows.append(dict(inp=r['inp'], imb_current=a['imb'], imb_fixed=b['imb'], out_same=a['sha'] == b['sha'],
                     cont_current=a['cont'], cont_fixed=b['cont']))
# the defect fired where the fix narrows the gap; gaps it leaves alone (1e-13 to 2e-12 cfs on large
# flows) are rounding, not this defect
fired = [x for x in rows if (x['imb_fixed'] or 0) < (x['imb_current'] or 0)]
summary = dict(networks=len(rows), defect_fired=len(fired),
               max_imb_current=max((x['imb_current'] or 0) for x in rows), max_imb_fixed=max((x['imb_fixed'] or 0) for x in rows),
               min_imb_where_fired=min((x['imb_current'] or 0) for x in fired) if fired else 0,
               max_imb_fixed_where_fired=max((x['imb_fixed'] or 0) for x in fired) if fired else 0,
               changed_where_defect_fired=sum(1 for x in fired if not x['out_same']),
               changed_elsewhere=sum(1 for x in rows if not x['out_same'] and x not in fired))
json.dump(dict(summary=summary, rows=rows), open(OUT, 'w'), indent=1)
print(summary)
for x in fired: print('  fired: %-50s %.2e -> %.2e  out same %s  cont %s -> %s' % (x['inp'][:50], x['imb_current'], x['imb_fixed'], x['out_same'], x['cont_current'], x['cont_fixed']))
