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
    v1sum = os.path.join(R, 'results', 'v1', 'summary.json')
    if os.path.exists(v1sum) and open(v1sum, 'rb').read() == open(os.path.join(R, 'results', 'summary.json'), 'rb').read():
        L += ['', '*The corpus tables below were run on engine v1 (29 to 31 October 2026). The reruns on v1.1 are in progress and will replace them; v1 and v1.1 write identical bytes on the 13 test networks.*']
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
Wf = S.get('whatif')
if Wf:
    codes = ', '.join(f"ERROR {k} ×{v}" for k, v in sorted(Wf['census_error_codes'].items(), key=lambda kv: -kv[1]))
    L += ['', f"**What-if: every DYNWAVE corpus model switched to KINWAVE** (`tools/corpus_gate.py --force-routing KINWAVE --modes {','.join(Wf.get('modes', ['11']))}`, interface-file models left out; rules {', '.join({'11': 'HEAD', '21': 'CAPACITY', '31': 'AREA'}[m] for m in Wf.get('modes', ['11']))}, loops iterated). Not how these models were built; it measures how often a real network has a fork or a loop.", '',
          '| | Models |', '|---|---|',
          f"| Switched to KINWAVE | {Wf['models']:,} |",
          f"| Stock runs it | {Wf['stock_ran']:,} (swmm5-kw identical in {Wf['identical']:,}, different in {Wf['different']}) |",
          f"| Stock stops on another input check (not a fork or loop) | {Wf['stock_other_errors']:,} (swmm5-kw gives the same report) |",
          f"| Stock refuses with ERROR 133 or 131 | {Wf['census']:,} |",
          f"| ... and swmm5-kw runs it to the end | {Wf['census_ran']:,} (per network, a median of {Wf['split_median']:g} split junction{'' if Wf['split_median'] == 1 else 's'} and {Wf['loop_median']:g} loop-closing link{'' if Wf['loop_median'] == 1 else 's'}, at most {Wf['split_max']:g} and {Wf['loop_max']:g}; routing continuity error beyond ±1% in {Wf['cont_over_1']}) |",
          f"| ... and swmm5-kw then stops on another check | {Wf['census_error']:,}" + (f" ({codes})" if codes else '') + ' |',
          f"| Inconclusive or stock crashes | {Wf['inconclusive'] + Wf['crash_same']} |"]
OL = os.path.join(R, 'results', 'whatif_outliers.json'); VCp = os.path.join(R, 'results', 'version_check.json')
if Wf and os.path.exists(OL):
    import collections
    O = json.load(open(OL)); cc = collections.Counter(o['cause'] for o in O)
    L += ['', f"The {len(O)} largest continuity errors among the switched models, traced with `tools/conduit_balance.sh` (`results/whatif_outliers.json`): "
          f"{cc.get('F1 at capacity', 0)} make water in conduits pinned at capacity (finding 1), {cc.get('F3 flat conduits', 0)} in flat conduits that never fill (finding 3), "
          f"{cc.get('model (stock DW also fails)', 0)} {'fails' if cc.get('model (stock DW also fails)', 0) == 1 else 'fail'} under stock DYNWAVE as well, {cc.get('not attributed (no conduit imbalance found)', 0) + cc.get('not attributed', 0)} not attributed. Three were made into trees and run through stock 5.2.4 (`results/tree_tests.md`)."]
if os.path.exists(VCp):
    V = json.load(open(VCp))['summary']; gap_old = max(V[k]['max_gap_old'] for k in ('HEAD', 'CAPACITY', 'AREA')); gap_new = max(V[k]['max_gap_new'] for k in ('HEAD', 'CAPACITY', 'AREA'))
    L += ['', f"Engine v1 against v1.1 on the {V['networks']:,} switched networks swmm5-kw routes (`tools/version_check.py`, `results/version_check.json`): output changed under HEAD in {V['HEAD']['changed']} "
          f"({V['HEAD']['changed_and_old_gap_closed']} of them where v1's allocation gap closed), under CAPACITY in {V['CAPACITY']['changed']} and under AREA in {V['AREA']['changed']}. "
          f"The largest allocation gap in any rule went from {gap_old:.2e} cfs (v1) to {gap_new:.1e} cfs (v1.1); "
          f"in the networks whose output changed it is now at most {max((x['m1']['imb_new'] or 0) for x in json.load(open(VCp))['rows'] if not x['m1']['out_same']):.1e} cfs, and every network whose output did not change has the same gap in both versions. See [Defects fixed in v1.1](#defects-fixed-in-v11)."]
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
