#!/usr/bin/env python3
"""Trace the largest continuity errors of the what-if pass to a cause.

  python3 tools/trace_outliers.py <build-dir> <kwbal> <corpus-dir> results/gate_whatif.jsonl results/whatif_outliers.json [N]

For the N (default 30) networks swmm5-kw routed with the largest |routing continuity error|:
  * run stock 5.2.4 (<build-dir>/stockseq) on the ORIGINAL file, as built (dynamic wave);
  * run the conduit-balance build (<kwbal>, from tools/conduit_balance.sh) on the copy switched to
    KINWAVE, HEAD + loops, and keep the conduits that lost the most water, how many steps each
    spent at full capacity, and whether its upstream node is a split junction;
  * count EPA's WARNING 04 (minimum elevation drop used) in that run's report.
Cause, in order: the model itself if stock DYNWAVE also misses by more than 50%; F1 if a leading
conduit spent steps at capacity; F3 if EPA wrote WARNING 04 and conduits lost water; otherwise
not attributed. This is a classification by signature, not a proof; see docs/VERIFICATION.md.
"""
import json, os, re, subprocess, sys, tempfile
B, KWBAL, C, REC, OUT = [os.path.abspath(x) for x in sys.argv[1:6]]
N = int(sys.argv[6]) if len(sys.argv) > 6 else 30
STOCK = os.path.join(B, 'stockseq')

def continuity(rpt):
    m = re.search(r'Flow Routing Continuity.*?Continuity Error \(%\) \.+\s+(\S+)', rpt, re.S)
    return m.group(1) if m else 'ERROR ' + ','.join(sorted(set(re.findall(r'ERROR (\d+)', rpt))))

def force_copy(src):
    t = open(src, encoding='latin-1').read()
    if re.search(r'(?mi)^\s*FLOW_ROUTING\s', t): t = re.sub(r'(?mi)^(\s*FLOW_ROUTING\s+)\S+', r'\g<1>KINWAVE', t)
    else: t = re.sub(r'(?mi)^\[OPTIONS\]\s*$', '[OPTIONS]\nFLOW_ROUTING         KINWAVE', t, count=1)
    fd, p = tempfile.mkstemp(prefix='.kwbal_', suffix='.inp', dir=os.path.dirname(src)); os.close(fd)
    open(p, 'w', encoding='latin-1').write(t); return p

recs = [json.loads(l) for l in open(REC)]
ran = [r for r in recs if r['census'] and r.get('m11', {}).get('rc') == 0 and not r['m11'].get('errors')
       and r['m11'].get('continuity') not in (None, 'nan', '-nan')]
ran.sort(key=lambda r: -abs(float(r['m11']['continuity'])))
rows = []
for r in ran[:N]:
    src = os.path.join(C, r['inp']); d = tempfile.mkdtemp()
    subprocess.run([STOCK, src, d + '/s.rpt', d + '/s.out'], cwd=os.path.dirname(src), capture_output=True, timeout=900)
    dw = continuity(open(d + '/s.rpt', encoding='latin-1').read())
    cp = force_copy(src)
    try:
        p = subprocess.run([KWBAL, cp, d + '/k.rpt', d + '/k.out'], env={'KWSPLIT': '1', 'KWLOOP': '1'}, cwd=os.path.dirname(src),
                           capture_output=True, text=True, timeout=900)
    finally:
        os.remove(cp)
    rpt = open(d + '/k.rpt', encoding='latin-1').read()
    top = []
    for l in p.stderr.splitlines():
        m = re.match(r'DBG link (\S+)\s+imb\s+(\S+) ft3\s+steps at cap\s+(\S+)\s+upstream node (\S+)( \(SPLIT\))?', l)
        if m: top.append(dict(link=m.group(1), imb_ft3=float(m.group(2)), steps_at_cap=float(m.group(3)), upstream=m.group(4), split=bool(m.group(5))))
    w04 = len(re.findall(r'WARNING 04', rpt))
    dwv = float(dw) if re.match(r'^-?\d', dw) else None
    if dwv is not None and abs(dwv) > 50: cause = 'model (stock DW also fails)'
    elif any(t['steps_at_cap'] > 0 for t in top[:3]): cause = 'F1 at capacity'
    elif w04 and top: cause = 'F3 flat conduits'
    else: cause = 'not attributed (no conduit imbalance found)' if not top else 'not attributed'
    rows.append(dict(inp=r['inp'], kw=r['m11']['continuity'], dw=dw, warn04=w04, top=top[:4], cause=cause))
    subprocess.run(['rm', '-rf', d])
    print('%-50s kw %9s  dw %9s  W04 %2d  -> %s' % (r['inp'][:50], r['m11']['continuity'], dw, w04, cause), flush=True)
json.dump(rows, open(OUT, 'w'), indent=1)
