# Decisions that are Bob's, still open

1. **Runtime switch or `.inp` keyword.** Today the modes live outside the file
   (`swmm_setKwOptions`, or `KWSPLIT`/`KWLOOP` for `kwswmm`), so one `.inp` can give ERROR 133
   or results depending on the caller. A semantics-changing feature normally gets a visible
   `[OPTIONS]` keyword; the August 2026 SWMM6 multi-outlet plan proposed
   `NODE_SPLIT NONE|HEAD|AREA|CAPACITY`, default NONE. Needed before any EPA pull request or
   regression-suite use.
2. **Version stamp.** The report header still says Build 5.2.4. `5.2.4-kw` would tell a reader
   of the report which engine wrote it, beyond the `KW/SF extension` block.
3. **Default rule.** The original ask (13 August 2026) was an AREA split. HEAD became the default
   because Claude recommended it; it has not been confirmed. On `split.inp` the two nearly agree:
   peak flows of 14.78 and 5.49 cfs under HEAD, 14.78 and 5.66 under AREA, against 14.27 and
   5.73 under dynamic wave. They will differ more below capacity.
4. **App default.** The Kleinian SWMM app turns the extension ON by default; the engine's default
   is OFF. `dist/swmm5-kw.html` runs both engines side by side and starts with HEAD and loops on.
5. **Apply the HEAD overshoot fix (v1.1).** `patch/kw-v1.1-head-overshoot.patch` closes a defect
   found on 31 October: when a junction's inflow sits within the bisection tolerance of one
   outlet's capacity, HEAD can hand out up to about 1.5e-6 cfs more than arrived (seen on corpus
   networks switched to KINWAVE; never on the shipped networks). The fix changes nothing on
   `models/`. Applying it changes the wasm, so the apps that embed `swmm524kw.wasm` would need the
   new file and the gates rerun ([DESIGN.md](DESIGN.md), "Open defect").
