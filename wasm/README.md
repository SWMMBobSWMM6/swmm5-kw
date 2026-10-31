# wasm/

| File | Bytes | SHA-256 | What |
|---|---|---|---|
| `swmm524kw.wasm` | 853,296 | `640115c4d1fff34cb586c5702c5199678cfdc2ba433b58ec09cfcafa1c2fd096` | EPA SWMM 5.2.4 + the KW/SF extension (`src/solver/`), wasm32-wasi reactor |
| `swmm524.wasm` | 840,503 | `9714657c0306f5673e287dbd1f71f371f8f3285fa8ad5542f0285db33f7f455f` | stock EPA SWMM 5.2.4 (this repository's first commit, `4cbd1eb`), same toolchain and flags |
| `kwengine.js` | | | runs either module: `new KWEngine(module).run(inpText, {split, loop, totalDays}, onProgress, shouldStop)` |
| `wasi-shim.iife.js` | | | [@bjorn3/browser_wasi_shim](https://github.com/bjorn3/browser_wasi_shim) 0.4.2, bundled to an IIFE with esbuild; sets `globalThis.WasiShim`. Licensed MIT OR Apache-2.0 by its authors |

Both `.wasm` files are rebuilt byte for byte by `tools/build.sh` with Ubuntu 24.04's clang 18.1.3, lld 18, wasi-libc 0.0~git20230113.4362b18-3 and libclang-rt-18-dev-wasm32:

```
clang-18 --target=wasm32-wasi --sysroot=/usr -mexec-model=reactor -O2 -w \
  -D_WASI_EMULATED_PROCESS_CLOCKS -D_WASI_EMULATED_SIGNAL -include tools/wasi_shims.h \
  -I src/solver -I src/solver/include src/solver/*.c -o swmm524kw.wasm \
  -Wl,--export=swmm_open ... -lwasi-emulated-process-clocks -lwasi-emulated-signal
```

v1.1 (31 October 2026) replaced v1.0's `swmm524kw.wasm` (853,130 bytes, sha256 `e62aa56968febce741d56de2f6e73660ead09fa700bad5071117b962b4939918`) after the fan-out fix in `kwmod.c`; apps that embed the old file should take this one and rerun the gates. The stock `swmm524.wasm` is unchanged.

wasi-libc's maths is musl's, so under kinematic wave these engines match a native **musl** build byte for byte, not a glibc build (docs/FINDINGS.md, F2). How to embed them in a page, a Replit app or a Node service: docs/INTEGRATION.md.
