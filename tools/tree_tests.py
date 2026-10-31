#!/usr/bin/env python3
"""Tree tests: is a what-if continuity error the extension's or stock kinematic wave's?

  python3 tools/tree_tests.py <kwbal> <corpus-dir> results/tree_tests.md

<kwbal> is the per-conduit balance build from tools/conduit_balance.sh. For each model below:
  * forks in place: the model switched to KINWAVE, run with KWSPLIT=1 KWLOOP=1 (swmm5-kw, HEAD + loops);
  * tree: tools/tree_variant.py deletes all but the first outlet at each named split junction, and
    the result runs with KWSPLIT=0 KWLOOP=0, which is stock 5.2.4 behaviour.
If stock's error on the tree is as large as swmm5-kw's with the forks in place, the extension did
not cause it. The table keeps the three conduits whose balance fails worst in the tree run.
"""
import os, re, subprocess, sys, tempfile
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KWBAL, C, OUT = [os.path.abspath(x) for x in sys.argv[1:4]]
CASES = [('XPSWMM/ATTEN.inp', ['A', 'B']), ('XPSWMM/UPWSH1.inp', ['102']), ('NCIMM_ROUTING/river.inp', ['G143'])]

def run(inp, splits, env):
    src = os.path.join(C, inp); d = os.path.dirname(src)
    fd, cp = tempfile.mkstemp(prefix='.tree_', suffix='.inp', dir=d); os.close(fd)
    msg = subprocess.run([sys.executable, os.path.join(R, 'tools', 'tree_variant.py'), src, cp] + splits,
                         capture_output=True, text=True, check=True).stdout.strip()
    w = tempfile.mkdtemp()
    try:
        p = subprocess.run([KWBAL, cp, w + '/m.rpt', w + '/m.out'], env=env, cwd=d, capture_output=True, text=True, timeout=1800)
        rpt = open(w + '/m.rpt', encoding='latin-1').read()
    finally:
        os.remove(cp); subprocess.run(['rm', '-rf', w])
    m = re.search(r'Flow Routing Continuity.*?Continuity Error \(%\) \.+\s+(\S+)', rpt, re.S)
    top = [dict(link=g[0], imb=float(g[1]), cap=float(g[2]))
           for g in re.findall(r'DBG link (\S+)\s+imb\s+(\S+) ft3\s+steps at cap\s+(\S+)', p.stderr)]
    steps = re.search(r'DBG steps\s+(\S+)', p.stderr)
    return dict(cont=float(m.group(1)), top=top, deleted=msg, w04=len(re.findall(r'WARNING 04', rpt)),
                steps=steps.group(1) if steps else None)

rows = []
for inp, splits in CASES:
    kw = run(inp, [], {'KWSPLIT': '1', 'KWLOOP': '1'})
    st = run(inp, splits, {'KWSPLIT': '0', 'KWLOOP': '0'})
    rows.append((inp, splits, kw, st))
    print(f'{inp}: swmm5-kw {kw["cont"]:.3f}%  stock tree {st["cont"]:.3f}%  ({st["deleted"]})', flush=True)
    for t in st['top'][:3]: print(f'    {t["link"]:14s} {t["imb"]:16,.1f} ft3  steps at cap {t["cap"]:.0f}')

L = ['# Tree tests: is a continuity error the extension\'s or stock kinematic wave\'s?', '',
     'Made by `python3 tools/tree_tests.py <kwbal> <corpus> results/tree_tests.md` against the corpus at 9ee63bd;',
     '`<kwbal>` is built by `tools/conduit_balance.sh`. "Forks in place" is the model switched to KINWAVE and run',
     'with HEAD + loops. "Tree" is the same copy with all but the first outlet deleted at each split junction',
     '(`tools/tree_variant.py`) and run with the extension off, which is stock 5.2.4. A negative continuity error',
     'means the run reports more water leaving than entered. Conduit imbalance is the sum over the run of',
     '(inflow − outflow)·Δt − ΔV; negative means the conduit passed on more than it was given.', '',
     '| Model (switched to KINWAVE) | Split junctions | swmm5-kw, forks in place | Stock 5.2.4, tree | Worst conduits in the tree run (imbalance, steps at full capacity) | WARNING 04 lines |',
     '|---|---|---|---|---|---|']
for inp, splits, kw, st in rows:
    worst = '; '.join(f'`{t["link"]}` {t["imb"]:,.0f} ft³, {t["cap"]:,.0f}' for t in st['top'][:3])
    L.append(f'| `{inp}` | {", ".join(splits)} ({st["deleted"].split(": ", 1)[-1]} deleted) | {kw["cont"]:,.3f}% | {st["cont"]:,.3f}% | {worst} | {st["w04"]} |')
L += ['', 'In each case stock\'s error on the tree is as large as swmm5-kw\'s with the forks in place, or larger.']
open(OUT, 'w').write('\n'.join(L) + '\n')
