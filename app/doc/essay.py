"""The Doc essay: one source, rendered into the app's Doc tab and into the .docx.

Every number comes from results/figdata.json (tools/figure_runs.py) or results/summary.json
(tools/summarize.py). Inline markup: **bold**, *italic*, `code`.
"""
import html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', '..', 'results')


def blocks(D, S):
    sh = {r['name']: r for r in D['split_shares']}
    dw, kh, sf, kc, ka = (sh['DYNWAVE (stock)'], sh['KINWAVE, HEAD'], sh['STEADY, HEAD'], sh['KINWAVE, CAPACITY'], sh['KINWAVE, AREA'])
    q = lambda r, i: r['total'] * r['share'][i]
    pct = lambda r, i: 100 * r['share'][i]
    la = D['nets']['loopactive']; lp = D['nets']['loop']
    lst = la['stats']
    peaks = D['peaks']
    def maxdev(models):
        v = [abs(p['kw'] - p['dw']) / p['dw'] for p in peaks if p['model'] in models and p['dw'] > 0.5]
        return 100 * max(v)
    sf_curve = D['section_factor']; pk = max(sf_curve, key=lambda c: c[1]); cross = next(y for y, v in sf_curve if v >= 1)
    chain = D['chain_sweep']; worst = min(chain, key=lambda c: c['musl'])
    ch = {c['q']: c['musl'] for c in chain}
    R1kw = max(D['loop_series']['kw']); R1dw = min(D['loop_series']['dw'])
    T = S.get('total', {}); P = {p['file']: p for p in S.get('passes', [])}; NSET = S.get('corpus_set', 0); W = S.get('whatif')
    kwp = P.get('gate_kwsf.jsonl', {}); dwp = P.get('gate_dw.jsonl', {}); ifp = P.get('gate_iface.jsonl', {})
    cen = S.get('census', [])
    cen_txt = ', '.join(f"`{c['inp']}`" for c in cen) or 'none'
    imb = max(n['stats'][3] for n in D['nets'].values())
    OUTL = D.get('outliers') or []; FX = (D.get('fixcheck') or {}).get('summary')
    flat = {(c['drop_ft'], c['q_cfs']): c['musl'] for c in D['flat_channel']}
    G = {g[0].split(':')[0]: g[1] for g in D['gates']['gates']}
    order_n = re.search(r'(\d+) of (\d+) networks', G['Order independence']).group(2)
    wasm_n = re.search(r'(\d+) of (\d+)', G['WebAssembly']).group(2)
    FO = D['fanout']; g10 = FO['runs']['v1.0']; g11 = FO['runs']['v1.1']
    w10 = max(range(FO['n']), key=lambda k: g10['gap'][k]); CEN = D['census']; APPC = D.get('appcheck') or {}
    fan_gate = G['Fan-out']

    B = []
    h1 = lambda t: B.append(('h1', t)); deck = lambda t: B.append(('deck', t)); h2 = lambda t: B.append(('h2', t))
    p = lambda t: B.append(('p', t)); fig = lambda k, c: B.append(('fig', k, c)); box = lambda kind, t: B.append(('box', kind, t))
    pre = lambda t: B.append(('pre', t)); ul = lambda items: B.append(('ul', items)); table = lambda hd, rows: B.append(('table', hd, rows))

    h1('Forks in the Road')
    deck('How swmm5-kw teaches EPA SWMM 5.2.4\'s kinematic wave and steady flow to split a junction and run a loop, what it proved about itself, and what it still cannot do.')

    h2('The one-way street')
    p('Kinematic wave is the plainest honest way to move water through a sewer model. Each pipe takes what its upstream junction hands it, runs that through Manning\'s equation and the continuity equation, and passes the result on. No pipe ever asks what is happening below it. That is why it is fast. It is also why it is fussy.')
    p('Because every pipe waits on its upstream junction, SWMM has to put the pipes in order before it routes a drop: each pipe after every pipe that feeds it. The ordering is called a topological sort, and `toposort.c` does it once, before the run. A network with one way out of every junction and no way back sorts cleanly. Mathematicians call that shape a tree. So do sewer designers, for the same reason.')
    p('Hand stock SWMM 5.2.4 anything else under KINWAVE or STEADY routing and it stops before it starts. A junction with two outlets gets you this:')
    pre('ERROR 133: Node J2 has more than one outlet link.')
    p('A path that leads back to where it began gets you this:')
    pre('ERROR 131: the following links form cyclic loops in the drainage system:')
    fig('tree', 'Stock SWMM routes kinematic wave and steady flow in one pass, upstream to downstream. A fork leaves the pass without a rule for dividing the water; a loop leaves it without a place to start.')

    h2('Why the rule is there')
    p('The rule is not an oversight. The engine knows exactly how much water reaches a junction. What it does not know is how to divide it. Dynamic wave never needs telling: it solves for the water surface at every node at once, and the head difference along each pipe settles the share. Kinematic wave has no head to speak of. It knows depth in a pipe, not level at a junction.')
    p('So SWMM gives you a node built for the job, the DIVIDER, with four ways to divide (CUTOFF, OVERFLOW, TABULAR and WEIR), and it makes you pick one and supply its numbers. The old Transport block worked the same way with its flow-divider elements. The position is "you tell me how the water splits, and I will route it." That is a sound engineering position.')
    p('It is also a tax. Real systems are full of forks: relief sewers, twin barrels laid forty years apart, a storm drain that parts around a building and meets itself on the other side. Each one has to become a divider, and each divider needs a curve somebody made up. A made-up curve is a guess dressed as data, and it does not get better because it sits in an input file.')
    p('In September 2026 Bob asked for a SWMM5 whose kinematic wave and steady flow would run loops and node bifurcations. swmm5-kw is that engine.')

    h2('What swmm5-kw is')
    p('swmm5-kw is EPA SWMM 5.2.4, built from the official `v5.2.4` tag, with seven source files changed: one new file, `kwmod.c`, and small edits to `flowrout.c`, `toposort.c`, `node.c`, `swmm5.c`, `swmm5.h` and `funcs.h`, 622 lines added and 4 removed. It has two switches, set through one new API call, `swmm_setKwOptions(split, loop)`. The split switch picks a rule for dividing a junction\'s outflow among its outlets. The loop switch lets a directed loop iterate within each routing step. Both start off. With both off the engine is stock 5.2.4, byte for byte, refusals included. Dynamic wave is never touched.')

    h2('One water level for every outlet')
    p('The default split rule is called HEAD, and it borrows the one idea kinematic wave lacks. Imagine water standing in the junction at some level, call it *y*. Every outlet pipe sees that level at its own entrance, less its own offset above the junction floor. At normal depth, each pipe carries whatever Manning\'s equation gives for that depth. Add up those flows. Too much water leaving? Lower *y*. Too little? Raise it. Halve the bracket each time, and after 22 to 31 halvings on average (in the test runs) you have the one level at which the outlets together carry exactly what came in.')
    fig('head', 'HEAD in elevation. The same level y fills each outlet to a different depth because each sits at a different height. The small pipe takes y minus its offset; the large pipe, with y above its crown, is full and capped.')
    p(f'There is one trap, and it is an old one. A circular pipe carries more than its full-pipe flow when it runs just short of full. The wetted perimeter shrinks faster than the area near the crown, so Manning\'s flow climbs past full at {cross:.2f} of the diameter and peaks at {pk[1]:.3f} times full flow at {pk[0]:.2f}. Let that curve run free and the total is no longer a steady climb in *y*, and a bisection can be fooled. So HEAD caps each outlet at its full-flow capacity. Water beyond the sum of the capacities stays in the junction and ponds or floods, which is exactly what SWMM\'s kinematic wave already does with a single pipe that is full.')
    fig('sfactor', f'Flow against depth in a circular pipe, from Manning\'s equation. The open-channel curve passes full-pipe flow at {cross:.2f} of the diameter and peaks {100 * (pk[1] - 1):.1f}% above it. HEAD uses the capped curve, which only ever rises.')
    p('The other two rules are simpler. CAPACITY divides in proportion to each outlet\'s full-flow capacity. AREA divides in proportion to each outlet\'s flow area at the end of the previous step, falling back to CAPACITY on the first step, when every area is zero. AREA was the first rule Bob asked for, in August 2026. All three compute every outlet of a junction together, once per sweep, so the answer cannot depend on which outlet happens to ask first.')

    h2('What the numbers say')
    p(f'The first test network, `split.inp`, is as small as a fork can be: one 3 ft pipe carrying 20 cfs into a junction with two outlets, a 3.0 ft pipe and a 1.5 ft pipe, both 400 ft long on the same slope. Stock 5.2.4 refuses it under kinematic wave with ERROR 133 and runs it under dynamic wave. swmm5-kw runs it under all three rules.')
    fig('shares', f'How split.inp divides its 20 cfs at the moment the total outflow peaks. HEAD and AREA put the 1.5 ft pipe at its full-flow capacity; dynamic wave pushes {q(dw, 1):.2f} cfs through it under pressure. CAPACITY sends far too much down the big pipe.')
    p(f'HEAD sends {pct(kh, 0):.1f}% of the flow down the big pipe. Dynamic wave sends {pct(dw, 0):.1f}%. The gap is not a flaw in the rule. It is the one thing dynamic wave can do that kinematic wave cannot: push a pipe past full. Dynamic wave drives {q(dw, 1):.2f} cfs through the 1.5 ft pipe, about {100 * (q(dw, 1) / q(kh, 1) - 1):.0f}% beyond the {q(kh, 1):.2f} cfs it can carry flowing full by gravity, because the junction\'s water surface rises and the pipe runs under pressure. Under kinematic wave, full is full. AREA lands in the same place here, because the small pipe is at its cap either way. CAPACITY sends {pct(kc, 0):.1f}% down the big pipe and misses by {pct(kc, 0) - pct(dw, 0):.0f} points. Capacity says what a pipe could carry flowing full, not what it takes when both pipes see the same water level.')
    fig('hydro', 'The whole storm at the fork in split.inp. Solid lines are swmm5-kw under KINWAVE with HEAD; dashed lines are stock EPA under DYNWAVE. The small outlet runs at its capacity through the plateau; dynamic wave puts it under pressure.')
    p(f'Two more networks split and rejoin: `diamond.inp`, one fork and one merge, and `braid.inp`, two of each. Every pipe\'s peak flow under swmm5-kw lands within {maxdev(["diamond", "braid"]):.1f}% of dynamic wave, and within {maxdev(["split"]):.1f}% on `split.inp`. Steady flow with HEAD gives a routing continuity error of {sf["cont"]:.3f}% on `split.inp`; kinematic wave gives {kh["cont"]:.3f}%, about what stock kinematic wave gives on the plain three-pipe chain at 30 cfs ({ch[30.0]:.3f}%).')
    fig('peaks', 'Peak flow in every link of the five test networks, swmm5-kw (KINWAVE, HEAD, loops iterated) against stock EPA under DYNWAVE. The splits sit on the line. The loops do not, for reasons the next two sections give. R1\'s dynamic-wave flow is negative all storm, so its peak plots at zero.')

    h2('Water that comes back')
    p('A loop breaks the sort itself. Kahn\'s algorithm, which `toposort.c` uses, repeatedly takes a junction whose inflows are all accounted for. In a loop, every junction is waiting on another, and the algorithm runs out of candidates with pipes still unsorted. Stock SWMM reports ERROR 131 at that point.')
    p('swmm5-kw instead picks one junction and declares its waiting over. It takes the unfinished junction with the fewest unsorted inflows; on a tie, the one with the most inflows already sorted, which is the loop\'s natural entrance; on a further tie, the smallest ID in alphabetical order. That last rule matters more than it looks. The first version broke ties by position in the input file, and the loop models\' continuity changed between 0.122% and 0.125% when the file\'s lines were shuffled. An engine whose answer depends on line order is not an engine you can trust. After sorting, any pipe that delivers water to a junction already processed is marked as loop-closing.')
    p('Then, each routing step, the engine has to route water it has not computed yet. It guesses. Each loop-closing pipe is assumed to deliver what it delivered last step. The engine sweeps the network in order, compares what each loop-closing pipe actually routed with the guess, and if they disagree, puts everything back the way it was at the start of the step and sweeps again with better guesses.')
    fig('loopstep', 'One routing step on a network with a loop. The snapshot is what makes this sound for kinematic wave: each trial sweep must start from the same pipe state, or water is counted twice.')
    p(f'"Puts everything back" is the important part. A kinematic-wave pipe carries its state from one step to the next: flow and area at both ends. A trial sweep changes that state. Sweep again without restoring it and the second trial starts from the first trial\'s answer, which is how you count water twice. After 60 sweeps, or as soon as the guesses stop changing, the engine books any remaining difference to the receiving junction, so the books balance whether the iteration settled or not. On `loopactive.inp`, a relief pipe that spills from the bottom of the network back to the top, it took {lst[5]:.2f} sweeps per step on average; {int(lst[7])} of {int(lst[4])} steps reached the cap, and the largest leftover was {lst[8]:.4f} cfs.')

    h2('The pipe that ran backwards')
    p(f'Here is the result that matters most, and it corrects something. In September this engine\'s write-up compared the flow in that relief pipe, R1, under the two methods: {R1kw:.2f} cfs under swmm5-kw, {abs(R1dw):.2f} cfs under dynamic wave, and called both of them recirculation. Claude wrote that comparison. It looked only at the size of the two flows. It never looked at their sign.')
    p(f'The sign is the whole story. Under dynamic wave, R1 runs backwards for the entire storm, from J1 to J3, down to {R1dw:.2f} cfs. The water at J1 stands higher than the water at J3, so the "relief" pipe becomes a second path downstream, beside the main line. That is what a relief pipe in that position would really do. Kinematic wave cannot run a pipe backwards. A link\'s direction is fixed by the way it is drawn in the input file. So under swmm5-kw, R1 can only carry water the way it points, from J3 back to J1, and it carries {R1kw:.2f} cfs spilling over its 3.5 ft offset.')
    fig('backwards', 'Flow in the relief pipe R1 of loopactive.inp. Dynamic wave runs it backwards all storm as a second path downstream. Kinematic wave cannot reverse a pipe, so swmm5-kw sends a small flow the way the pipe is drawn.')
    p(f'`loop.inp` shows the same thing harder. There dynamic wave sends 30 cfs through a 2 ft outlet under pressure, and kinematic wave, which caps the pipe at full flow, gets 12 cfs through it and floods the rest. Its routing continuity error is {lp["kw_cont"]:.2f}%. September\'s pipe-by-pipe accounting put all of that imbalance in the two pipes running exactly at capacity, every junction in balance: a stock kinematic-wave behaviour described below.')
    p('The lesson is plain, and it belongs on every result swmm5-kw produces for a loop: a kinematic-wave loop is honest only where the ground fixes the direction of every pipe in it, where nothing would ever run backwards. Where backwater would reverse a pipe, kinematic wave is answering a different question, and no amount of iteration will make it answer yours. Loops are exactly where backwater tends to govern. Treat a kinematic-wave loop as screening, never as design.')

    h2('Proof that nothing else moved')
    p('An engine change is easy to make and hard to trust, so this one was built to be checked by machine. The first promise is that where the extension has no work, it does nothing at all. Not "nearly nothing": the same bytes.')
    kw_ident = kwp.get('identical', 0); kw_n = kwp.get('models', 0)
    pending = [n for n, q in (('the dynamic-wave pass', dwp), ('the interface-file pass', ifp)) if not q]
    p(f'Bob\'s corpus of SWMM5 models (the 1729-SWMM5-Models-2030 repository) supplied the test. The same {NSET:,} models swmm5-rust was gated on went through stock 5.2.4 and swmm5-kw, side by side, with the same calling sequence. The {kw_n:,} models that route KINWAVE or STEADY ran four times through swmm5-kw: extension off, then each split rule with loops on. {kw_ident:,} of them gave a `.out` file identical to stock byte for byte, and a report identical apart from its three clock lines, in all four runs. ' + (f'The {dwp["models"]:,} dynamic-wave models ran with the extension switched on and were identical to stock in {dwp["identical"]:,} cases. ' if dwp else '') + (f'Models that share interface files ran one at a time, so two runs never wrote the same file: {ifp["identical"]:,} of {ifp["models"]:,} identical. ' if ifp else '') + (f'When this page was built, {" and ".join(pending)} {"were" if len(pending) > 1 else "was"} still running; the README has the current table. ' if pending else '') + f'Not one model differed. {T.get("crash_same", 0)} more are decks from the OpenSWMM 2026 code review that crash stock 5.2.4 outright; swmm5-kw crashes at the same point and leaves the same partial output, which says the extension changed nothing there and says nothing else, because what C does after a crash like that is undefined. {T.get("inconclusive", 0)} could not be compared at all, because stock 5.2.4 itself never finished.')
    p(f'And how many of those models did the extension actually change? {len(cen)}: {cen_txt}, which stock refuses with ERROR 131 and swmm5-kw runs. The corpus is a strong test that the extension leaves everything else alone and a weak test of the extension itself, because real models that need it have been converted to dividers or to dynamic wave long ago. The five small networks above are, so far, most of the evidence about the splits themselves.')
    if W:
        p(f'So the corpus was asked a harder question. Each of its {W["models"]:,} dynamic-wave models (all but those that share interface files) was copied with its routing switched to KINWAVE and run through both engines. That is not how anyone built those models, and many fail kinematic wave\'s other checks first (a regulator that does not leave a storage unit, for one). But it shows how often a real network has a fork or a loop. Stock 5.2.4 refused {W["census"]:,} of them with ERROR 133 or 131. swmm5-kw ran {W["census_ran"]:,} of those to the end. The other {W["census_error"]:,} stopped on a check the extension leaves alone: a conduit sloping uphill (ERROR 115, in {W["census_error_codes"].get("115", W["census_error_codes"].get(115, 0)):,} of them), a regulator that does not leave a storage unit (ERROR 139, {W["census_error_codes"].get("139", W["census_error_codes"].get(139, 0)):,}), or a fork with a pump or regulator among its outlets, which keeps stock\'s ERROR 133 ({W["census_error_codes"].get("133", W["census_error_codes"].get(133, 0)):,}). Of the {W["stock_ran"]:,} that stock could run under kinematic wave, {"every one" if W["identical"] == W["stock_ran"] else f'{W["identical"]:,}'} gave identical bytes from swmm5-kw{"" if W["identical"] == W["stock_ran"] else f' and {W["different"]} differed'}; another {W["stock_other_errors"]:,} stopped on an input check in both engines with the same report.')
        if W.get('census_ran'):
            p(f'Among the networks swmm5-kw ran, the median had {W["split_median"]:g} split junction{"" if W["split_median"] == 1 else "s"} and {W["loop_median"]:g} loop-closing link{"" if W["loop_median"] == 1 else "s"}; the largest had {W["split_max"]:,} and {W["loop_max"]:,}. Their kinematic-wave routing continuity errors had a median magnitude of {W["cont_median_abs"]:.2f}%, and {W["cont_over_1"]} of {W["census_ran"]} exceeded 1%. That says the extension runs real networks. It says nothing about whether their answers are right: these models were built for dynamic wave, and the backwater they depend on is exactly what kinematic wave leaves out.')
        if OUTL:
            import collections
            cc = collections.Counter(o['cause'] for o in OUTL)
            p(f'The large continuity errors were run down one at a time, with a build that keeps a volume balance for every conduit (`tools/conduit_balance.sh`). Almost all of those errors are negative, and in SWMM\'s arithmetic a negative continuity error means the run reports more water leaving than ever came in. Of the {len(OUTL)} largest, {cc.get("F1 at capacity", 0)} make their extra water in conduits pinned at full capacity and {cc.get("F3 flat conduits", 0)} in flat conduits that never fill: two stock kinematic-wave behaviours described below. {"The last is a deck" if cc.get("model (stock DW also fails)", 0) == 1 else str(cc.get("model (stock DW also fails)", 0)) + " are decks"} that makes water under stock dynamic wave too (it pumps 5 cfs out of an empty wet well).{" " + str(cc.get("not attributed (no conduit imbalance found)", 0) + cc.get("not attributed", 0)) + " could not be attributed." if cc.get("not attributed (no conduit imbalance found)", 0) + cc.get("not attributed", 0) else ""} Three were tested directly by deleting forks until stock 5.2.4 would route the network: `XPSWMM/ATTEN.inp`, `NCIMM_ROUTING/river.inp` and `XPSWMM/UPWSH1.inp`. Each time stock\'s error was as large as swmm5-kw\'s or larger. On UPWSH1 stock kinematic wave reports −10,069%: one ditch, full for every step of the run, hands on 39.6 million cubic feet more than it is given.')
    fig('corpus', 'The corpus gate. Every model stock 5.2.4 runs gives the same bytes from swmm5-kw, in every mode; the ones stock refuses for a loop or a fork, swmm5-kw runs.')
    p(f'Three more checks ran on the shipped networks. Shuffling the order of junctions and conduits in the input file changed nothing, in {order_n} networks with three shuffles each. On those networks no allocation created or destroyed water: the largest difference between what a junction handed out and what it had was {imb:.1e} cfs, which is arithmetic rounding. And the WebAssembly engine this page runs gave the same bytes as a native build of the same source on all {wasm_n} runs, provided the native build uses the same maths library. That proviso turned out to be a finding of its own. All three checks share one weakness, which the second outside review found: every shipped junction has two outlets, so none of them could catch a limit that only bites at sixty-five. The section after next tells that story.')

    if FX:
        p(f'The corpus found the one place where that is not true. In `XPSWMM/EXTUT17.inp` a junction feeds a 1 ft pipe that can carry 0.1126658 cfs and an overflow channel 100 ft up that can carry 14,812. At one step 0.1126642 cfs arrived, a hair under the small pipe\'s capacity. HEAD\'s bisection stops when it is within a tolerance set by the junction\'s total capacity:')
        pre('if ( fabs(f) <= 1.0e-10 * capSum ) break;')
        p(f'With 14,812 cfs of capacity, that tolerance is 1.48e-6 cfs, coarser than the gap between the inflow and the small pipe\'s capacity. The bisection stopped just past it, the pipe was marked full at 0.1126658 cfs, and the correction step that follows only adjusts outlets below their caps:')
        pre('if ( sumFree > 0.0 && qT > sumCapped )')
        p(f'Here the capped pipe alone was over the inflow, so nothing ran, and the junction handed out 1.48e-6 cfs it did not have. It happened in {FX["defect_fired"]} of the {FX["networks"]:,} corpus networks swmm5-kw routed, never more than {FX["max_imb_current"]:.2e} cfs. At its worst that is a rate of about five fluid ounces an hour. Still a defect: the engine promises never to make water. `patch/kw-v1.1-head-overshoot.patch` adds one branch, which scales every outlet down to the inflow when the capped ones alone exceed it. On all {FX["networks"]:,} networks it brings the largest gap to {FX["max_imb_fixed"]:.1e} cfs and changes output only where the defect fired. It is not applied. Version 1.1 changes the engine for another reason (the next section), so the apps that embed it need the new file anyway; whether this fix rides along is still Bob\'s decision.')

    h2('The sixty-fifth outlet')
    p(f'On 31 October Bob passed along a second outside review, of version 1.0. It graded the work 82 out of 100, a B minus. It credited the regression work: 65 runs across the 13 shipped networks, 15 shuffled-order tests and the CAPACITY rule matching the ratio of Manning capacities. Then it listed five ways the engine or this page could mislead. All five reproduced before anything was changed.')
    p(f'The first was in the engine. Build a junction with {FO["n"]} outlets, every one a 12 in pipe 400 ft long at 1% slope, feed it {FO["inflow"]:g} cfs, and give one outlet a flow limit of {FO["qlimit"]:g} cfs. Under the AREA rule with steady flow, list the limited outlet first and the junction hands out exactly what arrives. List it 65th and the junction comes up {g10["gap"][w10]:.4f} cfs short and floods, with a peak of {g10["flood"][w10]:.2f} cfs, while the run ends without an error and global continuity still prints 0.000%. Nothing was created; water was held back that should have gone on. The cause was one declaration in the proportional rules:')
    pre('char done[64];')
    p('CAPACITY and AREA divide the water in passes. Each pass shares what is left among the outlets that are not yet full, and an outlet whose share passes its capacity takes the capacity and is marked full. The marks lived in that array, and every use was guarded so it could not overrun:')
    pre('if ( idx < 64 && done[idx] ) continue;')
    pre('if ( AllocQ[L] > cap ) { AllocQ[L] = cap; if ( idx < 64 ) done[idx] = 1; capped = 1; }')
    p('The guard kept the array safe and made the arithmetic wrong. An outlet past the 64th could be capped but never marked, so the next pass counted it as still open, handed it a share of what was left, and cut it back to its cap again. The share it could not take was lost to the junction. The two-outlet test networks never came near the limit, which is how a correct-looking guard survived every gate.')
    fig('fanout', 'The review\'s junction: the capped outlet moved through all 65 positions in the file, AREA rule, steady flow. Rings: v1.0, exact until the 65th position, then 0.04 cfs short. Line: v1.1, exact at every position. Measured with both builds.')
    p(f'Version 1.1 keeps the full marks per link, sized when the network is read, so any number of outlets is handled the same way. At 64 outlets or fewer, v1.0 and v1.1 run the same instructions in the same order, and on every shipped network, in six combinations of rule and loop setting, they write identical `.out` files. A new gate builds the review\'s junction at 64, 65, 66 and 130 outlets, moves the capped outlet through the boundary positions, and runs all three rules under kinematic wave and steady flow: {fan_gate}. Before the fix the same gate failed 12 of its 78 runs, every AREA run with the capped outlet at position 65 or later.')
    p(f'Did any corpus result depend on the old limit? A census of all {CEN["models"]:,} models counted every node\'s outgoing links. {CEN["over_64"]} node{"" if CEN["over_64"] == 1 else "s"} in the whole corpus {"has" if CEN["over_64"] == 1 else "have"} more than 64: node `{CEN["node"]}` in `{CEN["model"]}`, {CEN["max_outlets"]} conduits that each leave it and come straight back, an artefact of a conversion from XPSWMM. That model routes dynamic wave, which the extension never touches, and switched to kinematic wave it stops on an input check before routing a drop. Both versions write identical files for it. So the corpus tables above stand for v1.1 as they are.')
    p('The other four findings were in this page, and all four were about trust in what it shows. Run `split.inp`, pick `diamond.inp`, and export without running again: the file was named for the diamond and held the split\'s numbers, because the export took its name from whatever was selected at the moment of the click:')
    pre("save((CUR.name || 'model').replace(/\\.inp$/i, '') + '_swmm5kw_peaks.csv', ...)")
    p('Now every run carries a record made when it starts: model, routing, rule, loop setting, time. The export takes its name and a header from that record, and the moment the inputs on the left stop matching it, the results dim and a note says which run they belong to.')
    p('Stop swmm5-kw part way through a long run and v1.0 still printed its green headline, "Stock EPA refuses this network; swmm5-kw routes it," because the verdict looked only for error messages, and a stopped run has none. Completion now comes first: a stopped run gets a verdict that says so, with how many reporting periods it wrote out of how many the file asks for, and no comparison table, chart or export is drawn from it.')
    p('Peak flows were signed maxima started at minus infinity. A refused run has no series, so its peak was exported as `-Infinity`; and the relief pipe R1, which dynamic wave runs backwards all storm at down to -3.34 cfs, showed a peak of 0 under dynamic wave, the largest of its values. The essay said so; the live table did not. The table and the export now carry each run\'s signed maximum, signed minimum and absolute peak, compare runs on the absolute peak, flag any link that runs backwards and in which run, and leave a missing series blank.')
    p('The last was the time axis. SWMM writes its first reporting period at the end of the first report step, not at the start, but the chart put sample *p* at *p* steps from the left edge, so every curve sat one step early and the last tick could fall outside the chart. The chart now reads each sample\'s time from the record it came in.')
    fig('timeaxis', 'Six hourly reporting periods on the chart\'s time axis. v1.0 drew the hour-1 sample at hour 0 and put the 6-hour tick past the chart\'s edge; v1.1 uses the times stored in the .out file.')
    p(f'Each of the four page findings has a check in a browser test that drives this page as a person would ({APPC.get("checks", 12)} checks in all). They fail on the v1.0 page and pass on v1.1.')

    h2('Three things stock 5.2.4 does by itself')
    p(f'Building and checking this engine meant running a great many kinematic-wave models, and three behaviours of unmodified EPA 5.2.4 came to light. None has anything to do with the extension. Each shows up on a network with nothing to split and no loop.')
    p(f'The first is a continuity error at capacity. Feed the chain less than its full-pipe capacity of 33.35 cfs and the routing continuity error is about a tenth of a percent. Feed it a little more and the error grows, steadily, to {worst["musl"]:.2f}% at {worst["q"]:g} cfs, four cfs over capacity, then drops back to {ch[38.0]:.2f}% at 38 cfs. The minus sign matters: the run reports more water leaving than came in. A model whose peak happens to sit in that band reports a tenth more water out than in. In September only three inflows were run, 30, 34 and 40 cfs, and the worst of the three was {ch[34.0]:.2f}%. The sweep found the band they had stepped over.')
    fig('chain', 'Stock EPA 5.2.4, kinematic wave, three 3 ft pipes in series: routing continuity error against the inflow held for two and a half hours. Measured every 0.5 cfs. The open rings are the three inflows measured in September.')
    p('The likely cause sits in `kinwave.c`. When a pipe\'s inflow reaches full-pipe flow, the solver sets its inlet area to full. Just below, it takes the lower of the two depths that carry that flow, because a circle carries full flow twice, once at 82% depth and once at 100%. A pipe hovering at capacity can flip between the two from one step to the next, a jump of about 18% of the full area, and every flip is booked as stored water that was never there. The sudden recovery at 38 cfs is not explained yet.')
    p('The second is that kinematic-wave answers depend on the maths library. The same source compiled against glibc and against musl agree for the first 241 minutes of a storm on the 30 cfs chain and then part company by up to 2% on the recession. Dynamic wave and steady flow gave identical answers under both libraries. So "the same engine" means little for kinematic wave unless you also say which `libm` it was linked against. The browser engine uses musl\'s mathematics, and its gate compares against a musl build for exactly that reason.')
    p(f'The third came out of the corpus. Kinematic wave makes water in flat channels, and makes relatively more the less water there is. Run one 1,000 ft trapezoidal channel with no fall at all and a steady 0.03 cfs for a day, and stock 5.2.4 reports a routing continuity error of {flat[(0.0, 0.03)]:.2f}%: eleven percent more water out than in. EPA flags such a channel with WARNING 04 and gives it a minimum fall, but the error stays. Give the channel a tenth of a foot of fall and the error is {flat[(0.1, 0.03)]:.2f}%; a full foot, {flat[(1.0, 0.03)]:.2f}%; at 3 cfs on a foot of fall, {flat[(1.0, 3.0)]:.2f}%. Old models converted from other programs are full of flat channels, which is why this showed up in the what-if pass. Where in `kinwave.c` the extra water comes from has not been traced.')
    fig('flat', 'Stock EPA 5.2.4, kinematic wave, one 1,000 ft trapezoidal channel, a steady inflow for one day: routing continuity error against the channel\'s fall, for three inflows. Measured.')

    h2('What this does not show')
    ul(['That kinematic wave can represent backwater, surcharge or flow reversal. It cannot, in a split or a loop or anywhere else. HEAD is an allocation at normal depth.',
        'That swmm5-kw\'s loop results are fit for design. Where a pipe in a loop would run backwards, the answer is wrong in direction, not just in size.',
        'How the three split rules compare across real networks. Five small test networks were compared with dynamic wave. The corpus contains one model the extension changes.',
        'Anything about dynamic wave, which the extension never touches.',
        'That every continuity error in the what-if pass is stock behaviour. The 30 largest were traced; three of them by a direct test, the rest by a matching signature. The long tail below them was not examined.',
        'That the HEAD overshoot fix is right for every network. It was checked on the networks the corpus routes and the shipped ones, and it is not applied.',
        'A Windows build. The engine was built and gated on Linux (GCC 13, musl 1.2.4) and as WebAssembly (Clang 18, wasi-libc). EPA\'s optional `.def` export file does not list the two new functions.',
        'That the corpus was rerun through v1.1. It was not; the outlet census above is the argument that it would give the same bytes.',
        'A full visual pass of this page in every browser. The browser checks drive headless Chromium.',
        'A person\'s review of the C changes, line by line. The checks above are mechanical.'])

    h2('How to use it')
    p('**In this page.** Pick a test network or drop in your own `.inp`, choose a rule, and press Run. The page runs stock EPA 5.2.4, swmm5-kw and a dynamic-wave reference, and shows whether stock refused the model, how each split junction shared its water, and every link\'s peak flow side by side. The Verify tab runs the gates in your browser.')
    p('**On your own machine.** `tools/build.sh` builds the extended engine as `kwswmm`, and stock 5.2.4 beside it. Run `KWSPLIT=1 KWLOOP=1 build/kw/kwswmm model.inp model.rpt model.out`. `KWSPLIT` takes 1 for HEAD, 2 for CAPACITY, 3 for AREA; unset means stock. EPA\'s own CMake build also works on this tree and gives `runswmm` and `libswmm5`, which behave as stock until a program calls `swmm_setKwOptions`.')
    p('**In another app.** `wasm/swmm524kw.wasm` with `wasm/kwengine.js` and `wasm/wasi-shim.iife.js` runs anywhere a browser or Node runs, with no compiler. For a SWMM5 tree of your own, apply `patch/swmm524-kw.patch`, then run the gates before calling it the same engine.')

    h2('AI use')
    p('This engine, its tests, this page and this essay were made with Claude, Anthropic\'s AI model, under the direction of Robert (Bob) Dickinson, who asked for kinematic wave and steady flow that run loops and bifurcations, asked for the AREA rule first, chose to keep the work in its own repository, and supplies the model corpus. The engine was written on 29 September 2026; the repository, the corpus gate, this page and the essay on 29 October 2026, with Claude Opus 5.5. Claude designed and wrote the C changes, the test networks, the drivers, the gates, the WebAssembly builds and the JavaScript that runs them, the figures and this text. The checks are mechanical: byte comparison against stock 5.2.4 built from EPA\'s tag, on the shipped networks and the corpus, and the wasm against native builds. Claude also made the September errors this essay corrects, about the relief pipe and the continuity sweep. On 31 October, for version 1.1, Claude reproduced the five faults in the second outside review Bob supplied, fixed the allocator and the page, and wrote the fan-out gate, the outlet census, the browser checks and the section on them; the 64-slot array it fixed was its own September code. No person has yet reviewed the C changes line by line.')
    return B


# ------------------------------------------------------------------ rendering
def inline_html(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', t)
    return t


def runs(t):
    """[(text, {'b':..,'i':..,'code':..})] for the docx builder."""
    out = []
    for part in re.split(r'(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)', t):
        if not part: continue
        if part.startswith('`'): out.append([part[1:-1], {'code': True}])
        elif part.startswith('**'): out.append([part[2:-2], {'b': True}])
        elif part.startswith('*'): out.append([part[1:-1], {'i': True}])
        else: out.append([part, {}])
    return out


def to_html(B, figs, P):
    h = []; n = 0
    for b in B:
        k = b[0]
        if k == 'h1': h.append(f'<h1>{inline_html(b[1])}</h1>')
        elif k == 'deck': h.append(f'<p class="deck">{inline_html(b[1])}</p>')
        elif k == 'h2': h.append(f'<h2>{inline_html(b[1])}</h2>')
        elif k == 'p': h.append(f'<p>{inline_html(b[1])}</p>')
        elif k == 'pre': h.append(f'<pre class="code">{html.escape(b[1])}</pre>')
        elif k == 'ul': h.append('<ul>' + ''.join(f'<li>{inline_html(i)}</li>' for i in b[1]) + '</ul>')
        elif k == 'box': h.append(f'<div class="box {b[1]}"><p>{inline_html(b[2])}</p></div>')
        elif k == 'fig':
            n += 1
            h.append(f'<figure><div class="chartbox">{figs[b[1]](P)}</div><figcaption><b>Figure {n}.</b> {inline_html(b[2])}</figcaption></figure>')
    return '\n'.join(h)


def to_json(B):
    out = []; n = 0
    for b in B:
        k = b[0]
        if k in ('h1', 'h2', 'deck', 'pre'): out.append(dict(kind=k, text=b[1]))
        elif k == 'p': out.append(dict(kind='p', runs=runs(b[1])))
        elif k == 'ul': out.append(dict(kind='ul', items=[runs(i) for i in b[1]]))
        elif k == 'box': out.append(dict(kind='box', runs=runs(b[2])))
        elif k == 'fig':
            n += 1; out.append(dict(kind='fig', key=b[1], n=n, caption=runs(b[2])))
    return out


def load_data():
    D = json.load(open(os.path.join(RES, 'figdata.json')))
    sp = os.path.join(RES, 'summary.json')
    S = json.load(open(sp)) if os.path.exists(sp) else {}
    rows = []
    for p in S.get('passes', []):
        lab = {'gate_kwsf.jsonl': 'KINWAVE, STEADY', 'gate_dw.jsonl': 'DYNWAVE', 'gate_iface.jsonl': 'Interface-file models'}[p['file']]
        txt = f"{p['identical']:,} identical" + (f" · {p['census_ran']} run" if p['census_ran'] else '') + (f" · {p.get('crash_same', 0)} crash as stock" if p.get('crash_same') else '') + (f" · {p['inconclusive']} inconclusive" if p['inconclusive'] else '') + (f" · {p['different']} DIFFERENT" if p['different'] else '')
        rows.append(dict(label=lab, n=p['models'], same=p['identical'], ran=p['census_ran'] + p['census_error'], inc=p['inconclusive'] + p.get('crash_same', 0), diff=p['different'], text=txt))
    D['corpus_fig'] = rows
    for key, fn in (('outliers', 'whatif_outliers.json'), ('fixcheck', 'head_fix_check.json'), ('gates', 'gates.json'), ('fanout', 'fanout_fig.json'),
                    ('census', 'outlet_census.json'), ('appcheck', 'app_review2.json')):
        fp = os.path.join(RES, fn)
        if os.path.exists(fp): D[key] = json.load(open(fp))
    return D, S
