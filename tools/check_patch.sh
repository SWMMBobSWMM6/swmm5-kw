#!/bin/bash
# Check that patch/swmm524-kw.patch, applied to pristine EPA SWMM 5.2.4, reproduces src/ exactly.
#   tools/check_patch.sh [/path/to/pristine/epa-5.2.4]
# Without an argument the pristine tree comes from this repository's first commit (4cbd1eb, EPA's tree
# as released), or from a fresh clone of USEPA tag v5.2.4 when that commit is absent (shallow clones).
set -e
R=$(cd "$(dirname "$0")/.." && pwd); T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
if [ -n "$1" ]; then cp -r "$1/src" "$T/src"
elif BASE=$(git -C "$R" rev-parse -q --verify epa-v5.2.4^{commit} 2>/dev/null || git -C "$R" rev-parse -q --verify 4cbd1eb^{commit} 2>/dev/null); then git -C "$R" archive "$BASE" src | tar -x -C "$T"
else git clone -q --depth 1 --branch v5.2.4 https://github.com/USEPA/Stormwater-Management-Model.git "$T/epa" && mv "$T/epa/src" "$T/src"; fi
(cd "$T" && patch -p1 --quiet < "$R/patch/swmm524-kw.patch")
diff -r "$T/src" "$R/src" >/dev/null && echo "src/ = pristine v5.2.4 + patch, byte for byte (7 files)" || { echo "src/ DIFFERS from pristine + patch"; exit 1; }
