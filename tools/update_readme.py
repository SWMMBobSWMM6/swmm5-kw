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
Wf = S.get('whatif')
if Wf:
    codes = ', '.join(f"ERROR {k} ×{v}" for k, v in sorted(Wf['census_error_codes'].items(), key=lambda kv: -kv[1]))
    L += ['', f"**What-if: every DYNWAVE corpus model switched to KINWAVE** (`tools/corpus_gate.py --force-routing KINWAVE --modes 11`, interface-file models left out). Not how these models were built; it measures how often a real network has a fork or a loop.", '',
          '| | Models |', '|---|---|',
          f"| Switched to KINWAVE | {Wf['models']:,} |",
          f"| Stock runs it | {Wf['stock_ran']:,} (swmm5-kw identical in {Wf['identical']:,}, different in {Wf['different']}) |",
          f"| Stock stops on another input check (not a fork or loop) | {Wf['stock_other_errors']:,} (swmm5-kw gives the same report) |",
          f"| Stock refuses with ERROR 133 or 131 | {Wf['census']:,} |",
          f"| ... and swmm5-kw runs it to the end | {Wf['census_ran']:,} (per network, a median of {Wf['split_median']:g} split junction{'' if Wf['split_median'] == 1 else 's'} and {Wf['loop_median']:g} loop-closing link{'' if Wf['loop_median'] == 1 else 's'}, at most {Wf['split_max']:g} and {Wf['loop_max']:g}; routing continuity error beyond ±1% in {Wf['cont_over_1']}) |",
          f"| ... and swmm5-kw then stops on another check | {Wf['census_error']:,}" + (f" ({codes})" if codes else '') + ' |',
          f"| Inconclusive or stock crashes | {Wf['inconclusive'] + Wf['crash_same']} |"]
OL = os.path.join(R, 'results', 'whatif_outliers.json'); FXp = os.path.join(R, 'results', 'head_fix_check.json')
if Wf and os.path.exists(OL):
    import collections
    O = json.load(open(OL)); cc = collections.Counter(o['cause'] for o in O)
    L += ['', f"The {len(O)} largest continuity errors among the switched models, traced with `tools/conduit_balance.sh` (`results/whatif_outliers.json`): "
          f"{cc.get('F1 at capacity', 0)} make water in conduits pinned at capacity (finding 1), {cc.get('F3 flat conduits', 0)} in flat conduits that never fill (finding 3), "
          f"{cc.get('model (stock DW also fails)', 0)} {'fails' if cc.get('model (stock DW also fails)', 0) == 1 else 'fail'} under stock DYNWAVE as well, {cc.get('not attributed (no conduit imbalance found)', 0) + cc.get('not attributed', 0)} not attributed. Three were made into trees and run through stock 5.2.4 (`results/tree_tests.md`)."]
if os.path.exists(FXp):
    X = json.load(open(FXp))['summary']
    L += ['', f"HEAD overshoot (open defect): in {X['defect_fired']} of the {X['networks']:,} switched networks swmm5-kw routes, a junction handed out more than arrived, at most {X['max_imb_current']:.2e} cfs. "
          f"With `patch/kw-v1.1-head-overshoot.patch` (not applied) the largest gap is {X['max_imb_fixed']:.1e} cfs, and output changes in {X['changed_where_defect_fired']} networks, all of them ones where the defect fired ({X['changed_elsewhere']} elsewhere; `tools/head_fix_check.py`, `results/head_fix_check.json`)."]
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
