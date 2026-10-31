#!/bin/bash
# Diagnostic build: swmm5-kw with a per-conduit volume balance printed to stderr at the end of
# the run. Use it to find where a kinematic-wave continuity error lives (which conduits, whether
# they sat at capacity, whether they leave a split junction). Not part of the engine.
#   tools/conduit_balance.sh [outdir]          builds outdir/kwbal (default build/kwbal)
#   KWSPLIT=1 KWLOOP=1 build/kwbal/kwbal model.inp model.rpt model.out
# Prints the total of (qin - qout) * dt - dV over every conduit, then the eight largest, with
# the number of steps each spent at full capacity and whether its upstream node is a split.
set -e
R=$(cd "$(dirname "$0")/.." && pwd)
OUT=$(mkdir -p "${1:-$R/build/kwbal}" && cd "${1:-$R/build/kwbal}" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cp -r "$R/src" "$T/src"
(cd "$T" && patch -p1 --quiet < "$R/tools/conduit_balance.patch")
gcc -O2 -D_FORTIFY_SOURCE=0 -U_FORTIFY_SOURCE -w -I"$T/src/solver" -I"$T/src/solver/include" \
    "$T"/src/solver/*.c "$R/tools/kwmain.c" -lm -o "$OUT/kwbal"
echo "built $OUT/kwbal"
