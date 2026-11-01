# Verification

The extension makes five promises. Each has a gate that checks it by machine, and every gate
writes its record into `results/`. The numbers live in those records and in the README's
results block, which `tools/update_readme.py` writes from them; this page says what each gate
proves, what it does not, and how to rerun it.

"Stock" always means unmodified EPA 5.2.4 built from the repository's first commit (`4cbd1eb`, EPA's tag unchanged), driven
by `tools/stockmain.c` with the same call sequence as the extended driver `tools/kwmain.c`
(open, start, step, end, report, close). `swmm_run` writes the report's time-series section
differently from an explicit step loop, so comparing `runswmm` with a stepped driver would
report differences that are not the extension's.

## The promises and their gates

| # | Promise | Gate | Tool |
|---|---|---|---|
| 1 | **Off means stock.** With both options off (the default) the bytes are stock 5.2.4, ERROR 133 and 131 included | Stock refusals reproduced with modes 0/0; corpus mode 00 identical on every KINWAVE/STEADY model | `tools/gates.py`, `tools/corpus_gate.py --modes 00,...` |
| 2 | **On changes nothing it has no business changing.** A network with nothing to split or loop gives stock's bytes in every mode | Null gate on the tree networks; corpus modes 11, 21, 31 on every model stock runs | `tools/null_gate.sh`, `tools/corpus_gate.py` |
| 3 | **No order dependence.** Shuffling `[JUNCTIONS]` and `[CONDUITS]` changes nothing, and neither does where an outlet sits in the file | Three seeded shuffles of each split and loop network; one junction with 63 to 130 outlets and a limited outlet first, 64th, 65th and last, three rules (v1 failed this past the 64th outlet: `docs/DESIGN.md`, "Defects fixed in v1.1") | `tools/order_check.py`, `tools/many_outlets.py` via `tools/gates.py` |
| 4 | **Conservation.** An allocation hands out exactly what arrived, up to the outlets' combined capacity; a loop's leftover is booked. Holds to rounding on every shipped network and every corpus network in v1.1; v1 broke it by up to 1.48e-6 cfs on 20 corpus networks (HEAD) and left water behind past the 64th outlet (CAPACITY, AREA) | Largest gap between flow allocated and flow available, over every step and rule (`swmm_getKwStats` v[3]); v1 against v1.1 on every corpus network that routes | `tools/gates.py`, `tools/version_check.py` |
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

## The what-if pass

Because the corpus barely exercises the extension, a fourth pass asks a harder question:
`tools/corpus_gate.py --force-routing KINWAVE --modes 11,21,31` copies each DYNWAVE model (interface-
file models left out) beside the original with its routing switched to KINWAVE, and runs the
copy through stock and through swmm5-kw. No one built those models for kinematic wave, so this
measures how often real networks contain a fork or a loop, and whether swmm5-kw routes them. It
does not measure whether the answers are right: those networks depend on the backwater that
kinematic wave leaves out. The record is `results/gate_whatif.jsonl`; the counts are in the
README's results block (`summary.json`, `whatif`). A 120 s cap per run applies.

It also extends the null-effect test to every switched model stock can route: there swmm5-kw must
give stock's bytes.

Large continuity errors among the networks swmm5-kw ran were traced one at a time with
`tools/conduit_balance.sh`, a diagnostic build that keeps a volume balance for every conduit and
lists the conduits whose volume balance fails worst (in every case seen, they delivered more than
they received), how many steps each spent at full capacity, and whether it
leaves a split junction. The 30 largest are classified in `results/whatif_outliers.json`:
compared with stock DYNWAVE on the original file, and assigned to finding F1 (extra water from conduits
at capacity), F3 (extra water from flat conduits that never fill, models with EPA's WARNING 04), the
model itself (stock DYNWAVE fails too), or not attributed. The F3 attribution was shown directly
on `XPSWMM/ATTEN.inp`, and F1 on `XPSWMM/UPWSH1.inp` and `NCIMM_ROUTING/river.inp`, by deleting
forks (`tools/tree_variant.py`) so stock 5.2.4 routes the network: stock's continuity error is then
as large as swmm5-kw's or larger (`results/tree_tests.md`, made by `tools/tree_tests.py`). For the
others it rests on the matching signature.

The same pass found the HEAD overshoot defect (`docs/DESIGN.md`, "Defects fixed in v1.1").

## What the gates missed, and the v1.1 reruns

v1's gates ran CAPACITY and AREA only on the five small split and loop networks, none with more
than three outlets at a junction, and the what-if pass ran HEAD only. So the defect that an outside
review found on 31 October 2026, capped outlets past the 64th lost by CAPACITY and AREA, had no
test that could reach it. v1.1 adds the outlet-count gate, and every corpus pass was rerun on the
v1.1 engine, the what-if pass now in all three rules (`--modes 11,21,31`). The v1 records are kept
in `results/v1/`. `tools/version_check.py` builds v1 from git history and runs v1 and v1.1 side by
side on every network the what-if pass routes, in all three rules (`results/version_check.json`).

The reruns gave every model the same verdict v1 did: no model different in any of the four passes,
the same one network refused by stock and run by swmm5-kw, the same 10 stock crashes and the same 11
models that could not be compared (README, results block). In the version check, HEAD output
changed in exactly the 20 networks where v1's HEAD defect fired, and CAPACITY and AREA output
changed in none.

Two records needed a second look. One what-if run, `OWA_EXTRAN/longTS_extran1.inp` under
CAPACITY, first came back different: it had hit the 120 s cap while writing a 2.1 GB report, so its
files were cut short. Run again alone with `--timeout 900`, it was identical to stock in `.out` and
`.rpt`; the record carries a `rerun` note. And in the interface-file pass, two models that read a
hotstart file (`IO-37_use-hotstart.inp` and `Individual_Infiltration_Per_Subcatchment_use_HS.inp`)
ran this time, where under v1 stock stopped with ERROR 331 (cannot open hot start interface file),
because a model run earlier in the reruns had saved that file. swmm5-kw matched stock byte for byte
both times. That is why the count of models stock stops on in that pass went from 45 to 43; the
engine had nothing to do with it. The gate runs in the corpus checkout, so files that models save
stay there between passes.

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

**31 October 2026** (v1.1): two allocation defects fixed (`docs/DESIGN.md`, "Defects fixed in
v1.1"), the outlet-count gate added, every gate rerun (all pass), v1 and v1.1 compared byte for byte
on the 13 test networks in six mode settings (78 runs, identical), and every corpus pass rerun on
v1.1, the what-if pass in all three rules. `tools/build.sh` rebuilds the new `swmm524kw.wasm`
(`8d57faa0…`) byte for byte in a second build directory.

## What a person has not checked

The C changes have not been reviewed line by line by anyone but their author (Claude). The gates
have run on one machine (Ubuntu 24.04, GCC 13.3, musl 1.2.4, Clang 18) and in Node 22 and
headless Chromium; not on Windows, not with MSVC, and not with EPA's optional `.def` export
build, which does not list the two new functions.
