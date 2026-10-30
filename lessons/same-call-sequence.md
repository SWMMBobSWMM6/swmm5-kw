# Gate like with like

**What happened.** The first null gate compared EPA's `runswmm` (which calls `swmm_run`) with the
extended engine's stepped driver, and the reports differed on networks the extension could not
touch. `swmm_run` and an explicit open/start/step/end/report/close sequence write the report's
time-series section differently.

**The rule.** The reference must be driven exactly as the engine under test is driven.
`tools/stockmain.c` is stock 5.2.4 with `tools/kwmain.c`'s call sequence and nothing else.
