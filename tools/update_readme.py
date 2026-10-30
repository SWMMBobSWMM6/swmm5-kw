#!/usr/bin/env python3
"""Rewrite the README's results block from results/gates.json and results/summary.json.

  python3 tools/update_readme.py
"""
import json, os
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
G = json.load(open(os.path.join(R, 'results', 'gates.json')))
sp = os.path.join(R, 'results', 'summary.json'); S = json.load(open(sp)) if os.path.exists(sp) else {}
F = json.load(open(os.path.join(R, 'results', 'figdata.json')))
L = ['<!-- RESULTS -->', f'Written by `tools/update_readme.py` from `results/`; the app\'s Verify tab and the Doc essay read the same files.', '',
     f'**Shipped test networks** (`python3 tools/gates.py build/kw`, {G["date"]}):', '', '| Gate | Result | |', '|---|---|---|']
cell = lambda s: str(s).replace('|', '\\|')
for g in G['gates']: L.append(f'| {cell(g[0])} | {cell(g[1])} | {"pass" if g[2] else "**FAIL**"} |')
NSET = sum(1 for l in open(os.path.join(R, 'results', 'corpus_set.txt')) if l.strip())
if S.get('passes'):
    T = S['total']
    L += ['', f'**Corpus** ([SWMMBobSWMM6/1729-SWMM5-Models-2030](https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030) at 9ee63bd, the {NSET:,}-model set swmm5-rust was gated on; `tools/corpus_gate.py`, {T["runs"]:,} engine runs):', '',
          '| Pass | Modes run through swmm5-kw | Models | Identical to stock | Refused by stock, run by swmm5-kw | Stock crashes, same crash | Different | Inconclusive |', '|---|---|---|---|---|---|---|---|']
    for p in S['passes']:
        L.append(f"| {p['label']} | {', '.join(p['modes'])} | {p['models']:,} | {p['identical']:,} | {p['census_ran']} | {p['crash_same']} | {p['different']} | {p['inconclusive']} |")
    L.append(f"| **All** | | **{T['models']:,}** | **{T['identical']:,}** | **{T['census_ran']}** | **{T['crash_same']}** | **{T['different']}** | **{T['inconclusive']}** |")
    L += ['', '"Identical" means the `.out` file byte for byte and the `.rpt` byte for byte after removing the three wall-clock lines, in every mode listed. Modes: 00 extension off, 11 HEAD + loops, 21 CAPACITY + loops, 31 AREA + loops. "Stock crashes": OpenSWMM 2026 code-review decks on which EPA 5.2.4 itself dies with a signal; swmm5-kw dies at the same point with the same partial output.']
    if S['census']: L.append('Refused by stock and run by swmm5-kw: ' + '; '.join(f"`{c['inp']}` (stock ERROR {', '.join(map(str, c['stock_errors']))}; swmm5-kw routing continuity {c['continuity']}% with HEAD)" for c in S['census']) + '.')
    if len(S['passes']) < 3:
        L.append(f"*Still running: {', '.join(n for n in ('the DYNWAVE pass', 'the interface-file pass') if not any((n.split()[1] in p['label']) or (n == 'the interface-file pass' and 'interface' in p['label']) for p in S['passes']))}. This table is updated when they finish.*")
    if S['inconclusive']: L.append('Inconclusive: ' + '; '.join(f"`{i['inp']}` ({i['why']})" for i in S['inconclusive']) + '.')
sh = {r['name']: r for r in F['split_shares']}
L += ['', '**Split against dynamic wave** (`split.inp`, 20 cfs into a 3.0 ft and a 1.5 ft outlet, at the moment the total outflow peaks; `tools/figure_runs.py`):', '',
      '| Routing and rule | 3.0 ft pipe | 1.5 ft pipe | Routing continuity |', '|---|---|---|---|']
for n in ('DYNWAVE (stock)', 'KINWAVE, HEAD', 'STEADY, HEAD', 'KINWAVE, CAPACITY', 'KINWAVE, AREA'):
    r = sh[n]; L.append(f"| {n} | {r['total'] * r['share'][0]:.2f} cfs ({100 * r['share'][0]:.1f}%) | {r['total'] * r['share'][1]:.2f} cfs ({100 * r['share'][1]:.1f}%) | {r['cont']:.3f}% |")
L.append('<!-- /RESULTS -->')
p = os.path.join(R, 'README.md'); t = open(p).read()
a = t.index('<!-- RESULTS -->'); b = t.index('<!-- /RESULTS -->') + len('<!-- /RESULTS -->')
open(p, 'w').write(t[:a] + '\n'.join(L) + t[b:])
print('README results block updated')
