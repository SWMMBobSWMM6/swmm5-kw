# swmm5-kw

**EPA SWMM 5.2.4 whose kinematic wave and steady flow split junctions and run directed loops, and change nothing else.**

Stock SWMM routes KINWAVE and STEADY in one upstream-to-downstream pass, so it needs a tree: a junction with two outlets stops the run with ERROR 133, a directed loop with ERROR 131. swmm5-kw lifts both. A split junction shares its outflow among its outlets by one of three rules; a loop is iterated within each routing step until the flow coming back around settles. Dynamic wave is untouched. Both features are **off by default**, and with them off the engine is stock 5.2.4 byte for byte, refusals included.

| | |
|---|---|
| Base | EPA SWMM 5.2.4, [USEPA/Stormwater-Management-Model](https://github.com/USEPA/Stormwater-Management-Model/tree/v5.2.4) tag `v5.2.4` (commit 7952ca8), imported unchanged as this repository's first commit, `4cbd1eb` |
| Change | the second commit, `5c6c060`: one new file (`src/solver/kwmod.c`) and edits to six, 622 lines added (587 not blank), 4 removed. `git diff 4cbd1eb 5c6c060` is the whole extension; [`patch/swmm524-kw.patch`](patch/swmm524-kw.patch) is the same change as a file |
| API | `swmm_setKwOptions(split, loop)` before `swmm_start`; `swmm_getKwStats(double v[10])` after `swmm_end` |
| Gates | see [Results](#results) |
| WebAssembly | [`wasm/swmm524kw.wasm`](wasm/) (the extension) and `wasm/swmm524.wasm` (stock), wasm32-wasi reactors, rebuilt byte for byte by `tools/build.sh`; [`wasm/kwengine.js`](wasm/kwengine.js) runs either in a browser or Node |
| App | [`dist/swmm5-kw.html`](dist/swmm5-kw.html): one file, stock EPA and swmm5-kw side by side with a dynamic-wave reference, the gates runnable in the browser, and a Doc tab (the essay is also [`dist/swmm5-kw-doc.docx`](dist/swmm5-kw-doc.docx)). Built by `app/build.py` |

## Why

Real systems have forks: relief sewers, twin barrels, a storm drain that parts around a building. Stock SWMM's answer under kinematic wave is a DIVIDER node with a rule you supply (CUTOFF, OVERFLOW, TABULAR or WEIR). swmm5-kw computes the division from the outlets' own hydraulics instead, so a forked network can be screened with kinematic wave or steady flow without hand-made divider curves, and a looped one can be run at all.

## What it does

**Split junctions.** A junction whose outlets are all ordinary conduits (no pump, regulator or DUMMY link) gets its outflow allocated once per sweep, all outlets together:

* **HEAD** (split mode 1): the one water level *y* at which `Σ min(cap_k, barrels·β·S(A(y − offset_k)))` equals the inflow, found by bisection. Each outlet is capped at its full-flow capacity; excess stays at the node, as kinematic wave already does for one full pipe.
* **CAPACITY** (2): in proportion to full-flow capacity.
* **AREA** (3): in proportion to last step's flow area.

Storage units and dividers keep their stock rules.

**Directed loops.** `toposort.c` breaks a cycle instead of stopping (fewest unsorted inflows, then most inflows already sorted, then smallest ID, so file order never decides) and flags the loop-closing links. Each routing step, the engine snapshots its state, guesses each loop-closing link's outflow from the previous step, sweeps, and repeats from the snapshot until the guesses settle (at most 60 sweeps, under-relaxed from sweep 20), then books any remainder to the receiving node so continuity is exact.

Full detail and the code map: [docs/DESIGN.md](docs/DESIGN.md).

## The limit that matters

Kinematic wave cannot run a pipe backwards, cannot surcharge it, and has no backwater. HEAD is an allocation at normal depth, not a water surface. In a split that mostly shows as a small difference: dynamic wave pushes a full pipe past its gravity capacity under pressure. In a loop it can be a different answer altogether: in both shipped loop networks, dynamic wave runs the relief pipe **backwards** as a second path downstream, and kinematic wave, whose links can only flow the way they are drawn, sends water the other way round. A kinematic-wave loop is honest only where the ground fixes the direction of every pipe in it. Treat loop results as screening, never design.

## Results

<!-- RESULTS -->
Written by `tools/update_readme.py` from `results/`; the app's Verify tab and the Doc essay read the same files.

**Shipped test networks** (`python3 tools/gates.py build/kw`, 2026-10-29):

| Gate | Result | |
|---|---|---|
| Null effect: networks with nothing to split or loop, modes 0/0, 1/1, 2/1, 3/1 against stock | 32 runs on 8 networks, 0 differences (.out bytes, .rpt bar clock lines) | pass |
| Stock refusals: options off reproduce stock's ERROR 133 / 131; options on run the network | 10 cases (ERROR 133: 6, ERROR 131: 4), KINWAVE and STEADY, all as expected | pass |
| Order independence: [JUNCTIONS] and [CONDUITS] shuffled, 3 seeds, HEAD + loops | 5 of 5 networks: link peaks and continuity identical | pass |
| Conservation: largest gap between flow allocated and flow available at any split junction, any step, three rules | 7.1e-15 cfs over 15 runs | pass |
| WebAssembly: swmm524kw.wasm against a native musl build, every network, every mode | 52 of 52 .out files byte-identical | pass |
| WebAssembly: swmm524.wasm (stock) against native musl stock | 13 of 13 .out files byte-identical | pass |
| Reproducible build: swmm524kw.wasm rebuilt by tools/build.sh | byte-identical to wasm/swmm524kw.wasm | pass |
| Reproducible build: swmm524.wasm rebuilt by tools/build.sh | byte-identical to wasm/swmm524.wasm | pass |
| Patch: patch/swmm524-kw.patch on pristine EPA v5.2.4 reproduces src/ | src/ = pristine v5.2.4 + patch, byte for byte (7 files) | pass |

**Corpus** ([SWMMBobSWMM6/1729-SWMM5-Models-2030](https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030) at 9ee63bd, the 3,759-model set swmm5-rust was gated on; `tools/corpus_gate.py`, 8,747 engine runs):

| Pass | Modes run through swmm5-kw | Models | Identical to stock | Refused by stock, run by swmm5-kw | Stock crashes, same crash | Different | Inconclusive |
|---|---|---|---|---|---|---|---|
| KINWAVE and STEADY | 00, 11, 21, 31 | 357 | 352 | 1 | 3 | 0 | 1 |
| DYNWAVE (and unrecognised routing) | 11 | 3,239 | 3,226 | 0 | 7 | 0 | 6 |
| Models sharing interface files, run one at a time | 00, 11 | 163 | 159 | 0 | 0 | 0 | 4 |
| **All** | | **3,759** | **3,737** | **1** | **10** | **0** | **11** |

"Identical" means the `.out` file byte for byte and the `.rpt` byte for byte after removing the three wall-clock lines, in every mode listed. Modes: 00 extension off, 11 HEAD + loops, 21 CAPACITY + loops, 31 AREA + loops. "Stock crashes": OpenSWMM 2026 code-review decks on which EPA 5.2.4 itself dies with a signal; swmm5-kw dies at the same point with the same partial output.
Refused by stock and run by swmm5-kw: `NCIMM_ROUTING/water.inp` (stock ERROR 131; swmm5-kw routing continuity -2.167% with HEAD).
Inconclusive: `OpenSWMM_Code_Review_2026/4-io/IO-02-time-options-accept-nan-inf-huge/IO-02_end-time-1e30.inp` (stock and swmm5-kw both reached the 2 GiB file-size cap; the first 2,147,483,648 bytes of their .out files are identical); `NCIMM_Training/EPA-5.1.013-InfilTrench/infiltration5_longerm.inp` (stock and swmm5-kw both reached the 2 GiB file-size cap; the first 2,147,483,648 bytes of their .out files are identical); `SWMM5_NCIMM/1220_Nodes.inp` (stock run hit the time cap); `SWMM5_NCIMM/4190_Nodes.inp` (stock run hit the time cap); `SWMM5_NCIMM/669_Subs_4500_Nodes.inp` (stock run hit the time cap); `SWMM5_NCIMM/indy_small.inp` (stock run hit the time cap); `Simon_EPA/Session38_100_Control_Rules.inp` (stock run hit the time cap); `z1000Years/1000yearSimulation_Case6.inp` (stock and swmm5-kw both reached the 2 GiB file-size cap; the first 2,147,483,648 bytes of their .out files are identical); `z1000Years/1000yearSimulation_Case1.inp` (stock and swmm5-kw both reached the 2 GiB file-size cap; the first 2,147,483,648 bytes of their .out files are identical); `z1000Years/1000yearSimulation_Case0.inp` (stock and swmm5-kw both reached the 2 GiB file-size cap; the first 2,147,483,648 bytes of their .out files are identical); `z1000Years/1000yearSimulation_Case0_wq.inp` (stock and swmm5-kw both reached the 2 GiB file-size cap; the first 2,147,483,648 bytes of their .out files are identical).

**What-if: every DYNWAVE corpus model switched to KINWAVE** (`tools/corpus_gate.py --force-routing KINWAVE --modes 11`, interface-file models left out). Not how these models were built; it measures how often a real network has a fork or a loop.

| | Models |
|---|---|
| Switched to KINWAVE | 3,218 |
| Stock runs it | 1,412 (swmm5-kw identical in 1,412, different in 0) |
| Stock stops on another input check (not a fork or loop) | 874 (swmm5-kw gives the same report) |
| Stock refuses with ERROR 133 or 131 | 925 |
| ... and swmm5-kw runs it to the end | 234 (per network, a median of 1 split junction and 0 loop-closing links, at most 15 and 8; routing continuity error beyond ±1% in 60) |
| ... and swmm5-kw then stops on another check | 691 (ERROR 115 ×583, ERROR 139 ×357, ERROR 133 ×323, ERROR 141 ×12) |
| Inconclusive or stock crashes | 7 |

The 30 largest continuity errors among the switched models, traced with `tools/conduit_balance.sh` (`results/whatif_outliers.json`): 18 make water in conduits pinned at capacity (finding 1), 11 in flat conduits that never fill (finding 3), 1 fails under stock DYNWAVE as well, 0 not attributed. Three were made into trees and run through stock 5.2.4 (`results/tree_tests.md`).

HEAD overshoot (open defect): in 20 of the 234 switched networks swmm5-kw routes, a junction handed out more than arrived, at most 1.48e-06 cfs. With `patch/kw-v1.1-head-overshoot.patch` (not applied) the largest gap is 1.8e-12 cfs, and output changes in 20 networks, all of them ones where the defect fired (0 elsewhere; `tools/head_fix_check.py`, `results/head_fix_check.json`).

**Split against dynamic wave** (`split.inp`, 20 cfs into a 3.0 ft and a 1.5 ft outlet, at the moment the total outflow peaks; `tools/figure_runs.py`):

| Routing and rule | 3.0 ft pipe | 1.5 ft pipe | Routing continuity |
|---|---|---|---|
| DYNWAVE (stock) | 14.27 cfs (71.3%) | 5.73 cfs (28.7%) | -0.002% |
| KINWAVE, HEAD | 14.78 cfs (73.8%) | 5.25 cfs (26.2%) | 0.131% |
| STEADY, HEAD | 14.75 cfs (73.7%) | 5.25 cfs (26.3%) | 0.000% |
| KINWAVE, CAPACITY | 17.31 cfs (86.4%) | 2.73 cfs (13.6%) | 0.135% |
| KINWAVE, AREA | 14.78 cfs (73.8%) | 5.25 cfs (26.2%) | 0.120% |
<!-- /RESULTS -->

The full verification record, with what each gate proves and how to rerun it: [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Three findings about stock 5.2.4

All three appear in unmodified EPA 5.2.4 on networks with nothing to split or loop ([docs/FINDINGS.md](docs/FINDINGS.md)):

1. **Kinematic wave makes water at and just above pipe capacity.** On the three-pipe chain, routing continuity is about 0.1% below the 33.35 cfs capacity, grows to **−10.18% at 37.5 cfs**, and drops back to −0.48% at 38 cfs. (Negative means more water reported leaving than entered.) On a corpus model switched to KINWAVE and made into a tree, stock reports **−10,069%**: one conduit at capacity for every step delivers 39.6 million ft³ more than it receives.
2. **Kinematic wave results depend on the maths library.** glibc and musl builds of the same source agree for 241 minutes of the 30 cfs chain, then differ by up to about 2%. Dynamic wave and steady flow are identical under both. The wasm engines match musl.
3. **Kinematic wave makes water in flat channels.** One flat 1,000 ft trapezoidal channel at 0.03 cfs reports a routing continuity error of −11.0% in a day (EPA's WARNING 04 case); with a 1 ft fall, −1.2%. Findings 1 and 3 account for 29 of the 30 largest continuity errors in the what-if pass above; the 30th is a deck that fails under stock dynamic wave too.

## Corrections to the September 2026 write-up

The engine is the same binary as on 29 September 2026 (the wasm's SHA-256 is unchanged). Rerunning everything for this repository corrected four things the September write-up (by Claude) said about it:

1. **The relief loop.** It compared R1's 0.51 cfs under swmm5-kw with 3.34 cfs under dynamic wave and called both recirculation. Under dynamic wave R1 runs backwards (J1 → J3) all storm; the 3.34 cfs is flow the other way. See [The limit that matters](#the-limit-that-matters).
2. **The continuity finding.** It sampled three inflows and reported −1.6% at 34 cfs as the problem. A sweep finds −10.2% at 37.5 cfs.
3. **The split table.** It listed HEAD on `split.inp` as 14.78 and 5.66 cfs (72.3%). Today's runs give 14.78 and 5.49 cfs as the peaks under HEAD (5.66 is AREA's), and the 1.5 ft pipe sits at its 5.25 cfs capacity through the plateau under both. The table above shows flows at the moment of peak total outflow, which avoids the brief peaks at the plateau's ends.
4. **"Allocations never create water."** True on every shipped network (largest gap 7.1e-15 cfs), not in general. On corpus networks switched to KINWAVE, HEAD can hand out up to 1.48e-6 cfs more than arrived when a junction's inflow sits within the bisection tolerance of one outlet's capacity. The cause, with the code: [docs/DESIGN.md](docs/DESIGN.md), "Open defect". A one-branch fix, `patch/kw-v1.1-head-overshoot.patch`, is checked but **not applied** ([DECISIONS.md](docs/DECISIONS.md), item 5).

## Building

```sh
tools/build.sh build/kw                       # kwswmm, stockseq, musl twins, both wasm (see the script for the toolchain)
KWSPLIT=1 KWLOOP=1 build/kw/kwswmm model.inp model.rpt model.out
python3 tools/gates.py build/kw               # every gate on models/, writes results/gates.json
python3 tools/corpus_gate.py build/kw /path/to/1729-SWMM5-Models-2030 results/gate_kwsf.jsonl \
        --list results/corpus_set.txt --routing KINWAVE,STEADY,STEADYFLOW --modes 00,11,21,31
python3 tools/summarize.py && python3 tools/update_readme.py
python3 app/build.py && node app/doc/build_docx.js          # dist/swmm5-kw.html and the .docx
```

EPA's own CMake build works unchanged on this tree (`cmake -S . -B build && cmake --build build`) and gives `runswmm` and `libswmm5`; they behave as stock until a program calls `swmm_setKwOptions`. `KWSPLIT`: 1 HEAD, 2 CAPACITY, 3 AREA, unset or 0 stock. `KWLOOP`: 1 iterate, unset or 0 stock.

## Using it in another app

Browser, Replit or Node: `wasm/swmm524kw.wasm` + `wasm/wasi-shim.iife.js` + `wasm/kwengine.js`, no compiler needed. Another SWMM5 tree: `patch -p1 < patch/swmm524-kw.patch`, then run the gates. Details, and the rules that bit: [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Repository layout

| Path | |
|---|---|
| `src/` | EPA's source tree with the extension applied (EPA's `README.md` is kept as `README-EPA.md`; `Build.md`, `CMakeLists.txt`, `bindings/`, `tests/` are EPA's, untouched) |
| `patch/` | the extension as a patch against pristine v5.2.4 |
| `models/` | 13 test networks: splits, loops, chains, storage, and dynamic-wave twins |
| `tools/` | build, gates, corpus gate, figure runs, the two command-line drivers |
| `wasm/` | the two WebAssembly engines and their JavaScript driver |
| `results/` | every gate record, the figure data, and summaries ([results/README.md](results/README.md)) |
| `docs/` | design, integration, verification, findings, open decisions |
| `lessons/` | what went wrong or nearly did, one page each |
| `app/`, `dist/` | the app's sources and the built app and essay |

## Open decisions

A runtime switch (today) or an `[OPTIONS]` keyword; a version stamp such as `5.2.4-kw`; HEAD or AREA as the default rule; whether apps start with the extension on. [docs/DECISIONS.md](docs/DECISIONS.md).

## AI use

This repository was produced with Claude, Anthropic's AI model, at the request of Robert (Bob) Dickinson, who asked for kinematic wave and steady flow that run loops and node bifurcations, asked for the AREA rule first, chose to keep the work in its own repository, and supplies the model corpus. Claude designed and wrote the C changes on 29 September 2026; on 29 October 2026 (Claude Opus 5.5) it rebuilt everything from EPA's tag in a fresh workspace, wrote the gate tools and ran the corpus gate, wrote the app, the figures, the essay and these documents, and found and corrected the three errors in its own September write-up listed above. The checks are mechanical: byte comparison against stock 5.2.4 built from the official tag, on the test networks and the corpus, and of the wasm against native builds. No person has yet reviewed the C changes line by line or rerun the gates on another machine.

## License and credit

EPA SWMM is a work of the U.S. Environmental Protection Agency, in the public domain. Version 5.2.4's engine is Lewis Rossman's design; the extension changes only the kinematic-wave and steady-flow layout checks and adds the allocation and loop iteration beside them. @bjorn3/browser_wasi_shim 0.4.2 (bundled in `wasm/wasi-shim.iife.js`) is licensed MIT OR Apache-2.0.
