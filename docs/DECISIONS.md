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
5. ~~**Apply the HEAD overshoot fix (v1.1).**~~ Decided 31 October 2026: applied, together with the
   fix for capped outlets past the 64th, as engine v1.1. Apps that embed `swmm524kw.wasm` need the
   new file (sha256 `8d57faa0…`); Kleinian SWMM v1.4.0 already has it ([DESIGN.md](DESIGN.md),
   "Defects fixed in v1.1").
