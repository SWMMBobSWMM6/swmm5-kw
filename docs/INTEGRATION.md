# Carrying the engine into another app

## The pieces

| File | What it is |
|---|---|
| `wasm/swmm524kw.wasm` | EPA SWMM 5.2.4 + extension, wasm32-wasi **reactor**, 853,130 bytes, sha256 `e62aa56968febce741d56de2f6e73660ead09fa700bad5071117b962b4939918` |
| `wasm/swmm524.wasm` | stock EPA SWMM 5.2.4, same toolchain and flags, 840,503 bytes, sha256 `9714657c0306f5673e287dbd1f71f371f8f3285fa8ad5542f0285db33f7f455f` |
| `wasm/wasi-shim.iife.js` | @bjorn3/browser_wasi_shim 0.4.2 bundled to a 22 KB IIFE; sets `globalThis.WasiShim` |
| `wasm/kwengine.js` | `new KWEngine(module).run(inpText, {split, loop, totalDays}, onProgress, shouldStop)` → `{rc, stopped, rpt, out, stats, ms}`; runs either wasm |
| `src/solver/` | the C source, EPA's tree with the extension applied |
| `patch/swmm524-kw.patch` | the same change as a patch against pristine v5.2.4 |

Exports of the extended module: `swmm_open/start/step/end/report/close`, `swmm_getMassBalErr`,
`swmm_getVersion`, `swmm_getWarnings`, `swmm_getError`, `swmm_setKwOptions`, `swmm_getKwStats`,
`malloc`, `free`, `memory`. The stock module has the same list without the two `Kw` functions.
Imports are WASI only (clock, `fd_*`, `path_open`, `path_unlink_file`, `path_remove_directory`,
`proc_exit`).

## Browser: single-file HTML, Replit, Vite

```js
// once: compile (embed as base64 in a single file, or fetch from /wasm/ in a Vite app)
const module = await WebAssembly.compile(bytes);
const engine = new KWEngine(module);
// each run: a fresh instance inside run(); files live in an in-memory directory
const r = await engine.run(inpText, { split: 1, loop: 1, totalDays }, f => bar(f), () => stopRequested);
// r.rpt (latin1 text), r.out (Uint8Array), r.stats = swmm_getKwStats v[0..9]
```

`dist/swmm5-kw.html` is a working example: both modules embedded, the same model run through
each, results side by side.

Rules that bit, or would have:

- **WASI paths must be relative.** The shim rejects absolute paths; `kwengine.js` uses `m.inp`,
  `m.rpt`, `m.out` in a preopened `.`. SWMM's scratch files (`swmmXXXXXX`, for RDII or rainfall
  interface files) land there too through the `mkstemp` shim in `tools/wasi_shims.h`.
- **Mirror `swmm_run`'s sequence.** After a successful `swmm_open`, always call `swmm_end`,
  `swmm_report` and `swmm_close`, even if `swmm_start` failed; otherwise error runs leave a
  truncated `.out`. Never call `swmm_close` after `swmm_run` (a double `fclose` traps in wasm).
- **Fresh instance per run.** SWMM keeps global state; instantiating from a compiled module is cheap.
- **Stepping in chunks.** `kwengine.js` steps for about 28 ms, then yields with `setTimeout`, so
  the page stays responsive and `shouldStop` works. A Web Worker is the cleaner home for long
  runs; the worker loads the shim and `kwengine.js` with `importScripts` and receives the bytes.
- **Silence the shim.** `new WASI(args, env, fds, { debug: false })`; the bundle logs every file
  operation otherwise.
- **Vite or Replit:** put the `.wasm` in `public/wasm/` and fetch it; do not import it through
  the bundler. No emscripten, no `EM_CACHE`, no COOP/COEP headers (single-threaded).
- **Content-security policies** that omit `wasm-unsafe-eval` block `WebAssembly.compile`. Catch
  it and tell the user; never fail silently.

Reading results: the `.out` file is the standard SWMM5 binary layout; system variable 11 is
total outflow, 10 flooding, 9 total lateral inflow. The report's `KW/SF extension` block lists
the split junctions and loop links; a regex over it gives the engine's own lists.

## Node service (BatchSWMM style)

The same wasm runs under Node: `eval` the shim bundle (or import the npm package), then use
`kwengine.js` unchanged; `tools/wasm_check.js` is a working example. For bulk runs a native
build is faster (`tools/build.sh`). Say which libm it uses in any report, because KW results
differ between glibc and musl (see [FINDINGS.md](FINDINGS.md)).

## Native: CMake, or another program

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
```

builds EPA's `runswmm` and `libswmm5` from the extended source. `runswmm` calls `swmm_run`
and never sets the options, so it behaves exactly as stock 5.2.4; a program that wants the
extension calls `swmm_setKwOptions` before `swmm_start`, as `tools/kwmain.c` does.
`tools/build.sh` builds that driver as `kwswmm`:

```sh
KWSPLIT=1 KWLOOP=1 build/kw/kwswmm model.inp model.rpt model.out
```

## A vendored SWMM5 tree (Swmm5-UI-Engine and friends)

`patch -p1 < patch/swmm524-kw.patch` from the tree root. It applies to pristine v5.2.4. A tree
with other edits (for example the consolidated-LID change in `lid.c`, `lid.h`, `lidproc.c`)
does not overlap: the extension touches only `flowrout.c`, `toposort.c`, `node.c`, `swmm5.c`,
`funcs.h`, `include/swmm5.h` and adds `kwmod.c`. After patching, run the gates
([VERIFICATION.md](VERIFICATION.md)); the null gate is the one that proves the host's other
edits did not interact.

## What a host app should show

- Which rule ran (HEAD, CAPACITY or AREA) and whether loops were iterated, on every result.
- A stock run beside the extended one for any model that splits or loops (stock gives ERROR 133
  or 131, which is the point), and a dynamic-wave run as the reference.
- The engine's split-junction and loop-link lists, and loop sweeps and steps at the cap.
- A plain statement that HEAD carries no backwater.
- That the results come from a modified engine. The report says so in its `KW/SF extension`
  block; don't strip it, and don't present extended results as stock EPA SWMM.

## Toward SWMM6

This is the SWMM5 prototype of the August 2026 multi-outlet plan. That plan found, by reading
the swmm6_rel source rather than running it, that SWMM6's KW and steady-flow paths hand the
full node inflow to every outlet (flow duplication at any multi-outlet node), that SWMM6 has no
port of `storage_getOutflow`, and that it ignores `qLimit` under KW/SF. Those parity repairs
come before porting this allocator. The loop iteration has no counterpart in that plan and
would need its own design review there.
