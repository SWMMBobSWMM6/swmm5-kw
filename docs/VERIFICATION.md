# Verification

The extension makes five promises. Each has a gate that checks it by machine, and every gate
writes its record into `results/`. The numbers live in those records and in the README's
results block, which `tools/update_readme.py` writes from them; this page says what each gate
proves, what it does not, and how to rerun it.

"Stock" always means unmodified EPA 5.2.4 built from the repository's tag `epa-v5.2.4`, driven
by `tools/stockmain.c` with the same call sequence as the extended driver `tools/kwmain.c`
(open, start, step, end, report, close). `swmm_run` writes the report's time-series section
differently from an explicit step loop, so comparing `runswmm` with a stepped driver would
report differences that are not the extension's.

## The promises and their gates

| # | Promise | Gate | Tool |
|---|---|---|---|
| 1 | **Off means stock.** With both options off (the default) the bytes are stock 5.2.4, ERROR 133 and 131 included | Stock refusals reproduced with modes 0/0; corpus mode 00 identical on every KINWAVE/STEADY model | `tools/gates.py`, `tools/corpus_gate.py --modes 00,...` |
| 2 | **On changes nothing it has no business changing.** A network with nothing to split or loop gives stock's bytes in every mode | Null gate on the tree networks; corpus modes 11, 21, 31 on every model stock runs | `tools/null_gate.sh`, `tools/corpus_gate.py` |
| 3 | **No order dependence.** Shuffling `[JUNCTIONS]` and `[CONDUITS]` changes nothing | Three seeded shuffles of each split and loop network | `tools/order_check.py` |
| 4 | **Exact conservation.** An allocation never creates water; a loop's leftover is booked | Largest `|Σ allocated − min(available, Σ capacity)|` over every step, every rule (`swmm_getKwStats` v[3]) | `tools/gates.py` |
| 5 | **One engine, one answer.** The wasm engine is the same engine | `.out` bytes of `swmm524kw.wasm` against native musl, every network, every mode; the same for the stock wasm | `tools/wasm_check.js` |

Plus two reproducibility checks: `tools/build.sh` rebuilds both `.wasm` files byte for byte, and
`tools/check_patch.sh` confirms that `patch/swmm524-kw.patch` applied to pristine v5.2.4
reproduces `src/` exactly.

"Identical" means the `.out` file byte for byte and the `.rpt` byte for byte after removing the
three wall-clock lines (`Analysis begun on`, `Analysis ended on`, `Total elapsed time`).

## The corpus gate

`tools/corpus_gate.py` runs each model of a list through stock and through swmm5-kw once per
mode, with the caps swmm5-rust's gate used (3 GiB address space, 2 GiB per file, 300 s per run,
two at a time). The list is `results/corpus_set.txt`: the 3,759 models of
[SWMMBobSWMM6/1729-SWMM5-Models-2030](https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030)
(commit 9ee63bd) that swmm5-cplus and swmm5-rust were gated on. Three passes:

1. Models whose `FLOW_ROUTING` is KINWAVE or STEADY (or absent, which means KINWAVE), modes
   00, 11, 21 and 31: the only models the extension can act on.
2. Models routed DYNWAVE (or with a routing keyword 5.2.4 rejects), mode 11: the extension is
   on but has nothing to do.
3. The 163 models that read or write interface files (`results/interface_models.txt`, from
   swmm5-rust), modes 00 and 11, one at a time: run in parallel, two models in one folder can
   share a file.

`tools/summarize.py` classifies each model: **identical** in every mode; **refused by stock,
run by swmm5-kw** (stock stopped with ERROR 131 or 133, mode 00 reproduced that exactly, and the
modes with the extension on ran without an error); **stock crashes, same crash** (a code-review
deck on which stock dies with a signal and swmm5-kw dies at the same point with the same partial
output; C's behaviour there is undefined, so this shows only that the extension did not change
it); **inconclusive** (stock did not finish: the time cap or the 2 GiB file cap); **different**
(anything else; there have been none).

What the corpus shows: the extension leaves alone every model it has no business changing.
What it does not show: much about the extension itself. Real models that need a split or a loop
under kinematic wave have long since been converted to dividers or to dynamic wave, so the
corpus contains one model stock refuses for a loop and none it refuses for a fork. The evidence
about the split rules is the five small networks in `models/`.

## Comparison with dynamic wave

`tools/figure_runs.py` runs the split and loop networks under swmm5-kw and under stock dynamic
wave, sweeps the chain's inflow from 20 to 46 cfs, and writes `results/figdata.json`, which
every chart in the essay and the split table in the README read. It uses the musl builds,
because the wasm engines the app runs match them; on these networks the glibc builds give the
same split flows and continuity to the reported precision.

## History

**29 September 2026** (first build, in the Kleinian SWMM session): the null gate on 36 tree
models (Kleinian presets in DW, KW and SF, SI and US, chains, a flooding tree, storage) × 4
mode settings, 144 runs, identical; stock refusals reproduced; order independence on 8 split
and loop cases; conservation 8.9e-16 cfs; wasm against native musl 124 of 124. Those 36 models
are not in this repository.

**29 October 2026** (this repository): the patch applied cleanly to a fresh checkout of EPA's
tag, and `tools/build.sh` rebuilt `swmm524kw.wasm` with the same SHA-256 as September's, so the
engine is the same binary. Every gate above was rerun, the corpus gate was run for the first
time, and three statements in the September write-up were corrected (README, "Corrections").

## What a person has not checked

The C changes have not been reviewed line by line by anyone but their author (Claude). The gates
have run on one machine (Ubuntu 24.04, GCC 13.3, musl 1.2.4, Clang 18) and in Node 22 and
headless Chromium; not on Windows, not with MSVC, and not with EPA's optional `.def` export
build, which does not list the two new functions.
