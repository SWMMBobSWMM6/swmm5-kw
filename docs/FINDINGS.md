# Two behaviours of stock EPA SWMM 5.2.4

Both surfaced while building the extension. Neither is caused by it: they appear in
unmodified 5.2.4 on plain three-pipe chains with nothing to split and no loop. Remeasured on
29 October 2026 with the builds from `tools/build.sh`; the numbers match those first measured
on 29 September.

## F1. Kinematic wave loses continuity when a pipe runs right at capacity

`models/chain30.inp`, `chain34.inp`, `chain40.inp`: three 3 ft circular pipes in series, full-flow
capacity 33.35 cfs, an inflow that ramps to 30, 34 or 40 cfs, holds for 2.5 hours and recedes.
Stock 5.2.4, routing continuity error:

| Inflow | glibc build | musl build (and wasm) |
|---|---|---|
| 30 cfs | 0.124% | 0.124% |
| 34 cfs | **−1.596%** | **−1.599%** |
| 40 cfs | −0.064% | −0.064% |

September measured those three. On 29 October `tools/figure_runs.py` swept the held inflow from
20 to 46 cfs in steps of 0.5 (`results/figdata.json`, `chain_sweep`) and found the three points
had missed the worst of it:

| Inflow (cfs) | 33.0 | 33.5 | 34 | 35 | 36 | 37 | **37.5** | 38 | 40 |
|---|---|---|---|---|---|---|---|---|---|
| Continuity, glibc (%) | 0.155 | −0.266 | −1.596 | −4.180 | −6.639 | −9.029 | **−10.180** | −0.479 | −0.064 |
| Continuity, musl (%) | 0.155 | −0.267 | −1.599 | −4.179 | −6.639 | −9.030 | **−10.181** | −0.481 | −0.064 |

Below capacity the error is a tenth of a percent. From 33.5 cfs it grows steadily to −10.2% at
37.5 cfs, four cfs above capacity, then falls back to half a percent at 38 cfs. A model whose
peak happens to sit in that band reports losing a tenth of its water.

Likely cause, from reading `kinwave.c`: `kinwave_execute` sets a conduit's inlet area to full
when its inflow is at or above Qfull, and to the lower root of S(A) when the inflow is just
below. A circular pipe's S(A) passes Qfull at 82% depth and comes back to it at full, so a pipe
whose inflow hovers at capacity flips its inlet area by about 18% of the full area from one
step to the next, and `setNewLinkState` books the change in stored volume each time. The
per-link imbalance on `loop.inp` (below) sits in exactly such pipes. The sweep's sudden recovery
at 38 cfs is not explained yet.

The extension makes the regime easier to reach in one case: a loop recirculates flow into
pipes already near capacity. On `models/loop.inp` the routing continuity is −2.24%, and the
imbalance sits in the two equal pipes C1 and C2 that run at exactly full capacity (−4,902 and
−2,911 ft³ cumulative), while every node balances. It does not move with the 60-sweep cap
(tried 400) or the routing step (5, 2 and 1 s). The extension did not create the effect and
does not protect against it.

## F2. Kinematic wave results depend on the maths library

The same source compiled against glibc and against musl gives different KW results:

* gcc -O2, gcc -O0 and clang -O2 builds against glibc agree bit for bit.
* A musl build agrees with them for the first 241 of 360 one-minute report periods of
  `chain30.inp`, then differs on the recession: 1,844 of 20,160 stored values, by up to 1.9%
  (first difference measured in September: node 2 depth 0.3580 ft against 0.3548 ft, link 1
  flow 1.018 against 0.999 cfs).
* `chain34.inp` differs by up to 6.6%, `chain40.inp` by up to 1.8%.
* The wasm engines link wasi-libc, whose maths is musl's, and match the musl build byte for byte.
* Dynamic wave and steady flow gave identical results under both libraries on every model tried.

So a claim that two KW runs come from "the same engine" needs the libm named. That is why
this repository's wasm gate compares against native musl builds, and why
[VERIFICATION.md](VERIFICATION.md) says which build each number comes from.

Both findings belong in a SWMM regression suite as invariants that stock 5.2.4 currently fails.
