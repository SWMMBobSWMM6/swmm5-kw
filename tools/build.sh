#!/bin/bash
# Build the KW/SF extension and the stock reference it is gated against.
#
#   tools/build.sh [outdir] [/path/to/pristine/epa-5.2.4-source]
#
# outdir (default build/kw) receives:
#   kwswmm          the extended engine, test driver: KWSPLIT=1 KWLOOP=1 kwswmm in.inp out.rpt out.out
#   stockseq        unmodified EPA 5.2.4 driven by the same call sequence (for the gates)
#   kwswmm-musl, stockseq-musl   the same against musl libm (needs apt musl-tools); the wasm
#                   engines match these bit for bit, the glibc builds they do not (KW and libm)
#   swmm524kw.wasm, swmm524.wasm  wasm32-wasi reactors (needs clang-18, lld-18, wasi-libc,
#                   libclang-rt-18-dev-wasm32); compared against wasm/ in the repo
#
# The pristine EPA source comes from, in order: the second argument; this repository's own
# tag epa-v5.2.4 (absent in a shallow clone); a fresh clone of USEPA tag v5.2.4.
set -e
R=$(cd "$(dirname "$0")/.." && pwd)
OUT=$(mkdir -p "${1:-$R/build/kw}" && cd "${1:-$R/build/kw}" && pwd)
S="$R/src/solver"

if [ -n "$2" ]; then EPA=$(cd "$2" && pwd)
elif git -C "$R" rev-parse -q --verify epa-v5.2.4^{commit} >/dev/null 2>&1; then
  EPA="$OUT/epa-v5.2.4"; rm -rf "$EPA"; mkdir -p "$EPA"
  git -C "$R" archive epa-v5.2.4 src | tar -x -C "$EPA"
else
  EPA="$OUT/epa-v5.2.4"; rm -rf "$EPA"
  git clone -q --depth 1 --branch v5.2.4 https://github.com/USEPA/Stormwater-Management-Model.git "$EPA"
fi
P="$EPA/src/solver"

CF="-O2 -D_FORTIFY_SOURCE=0 -U_FORTIFY_SOURCE -w"   # glibc fortify aborts stock 5.2.4 builds on relative paths
gcc $CF -I"$S" -I"$S/include" "$S"/*.c "$R/tools/kwmain.c"    -lm -o "$OUT/kwswmm"
gcc $CF -I"$P" -I"$P/include" "$P"/*.c "$R/tools/stockmain.c" -lm -o "$OUT/stockseq"
echo "native (glibc): kwswmm, stockseq"
if command -v musl-gcc >/dev/null; then
  musl-gcc $CF -I"$S" -I"$S/include" "$S"/*.c "$R/tools/kwmain.c"    -lm -o "$OUT/kwswmm-musl"
  musl-gcc $CF -I"$P" -I"$P/include" "$P"/*.c "$R/tools/stockmain.c" -lm -o "$OUT/stockseq-musl"
  echo "native (musl): kwswmm-musl, stockseq-musl"
fi

if command -v clang-18 >/dev/null && [ -d /usr/lib/wasm32-wasi ]; then
  wasm() {  # $1 solver dir, $2 output, $3 extra exports
    local EXP=""
    for e in swmm_open swmm_start swmm_step swmm_end swmm_report swmm_close swmm_getMassBalErr \
             swmm_getVersion swmm_getWarnings swmm_getError $3 malloc free; do EXP="$EXP -Wl,--export=$e"; done
    clang-18 --target=wasm32-wasi --sysroot=/usr -mexec-model=reactor -O2 -w \
      -D_WASI_EMULATED_PROCESS_CLOCKS -D_WASI_EMULATED_SIGNAL -include "$R/tools/wasi_shims.h" \
      -I"$1" -I"$1/include" "$1"/*.c -o "$2" $EXP -lwasi-emulated-process-clocks -lwasi-emulated-signal
  }
  wasm "$S" "$OUT/swmm524kw.wasm" "swmm_setKwOptions swmm_getKwStats"
  wasm "$P" "$OUT/swmm524.wasm" ""
  for w in swmm524kw.wasm swmm524.wasm; do
    if cmp -s "$OUT/$w" "$R/wasm/$w"; then echo "wasm: $w byte-identical to wasm/$w"
    else echo "wasm: $w DIFFERS from wasm/$w (different toolchain or source): run the gates before shipping it"; fi
  done
else
  echo "wasm: skipped (needs clang-18, lld-18, wasi-libc, libclang-rt-18-dev-wasm32)"
fi
echo "built in $OUT"
