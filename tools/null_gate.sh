#!/bin/bash
# Null-effect gate: on models the extension has nothing to do with (trees, storage outlets),
# every mode setting must give .out bytes and .rpt text identical to stock 5.2.4.
#   scripts/null_gate.sh <build-dir> model1.inp model2.inp ...
B=${1:?usage: null_gate.sh <build-dir> models...}; shift
n=0; bad=0; T=$(mktemp -d)
for f in "$@"; do b=$(basename "${f%.*}")
  "$B/stockseq" "$f" "$T/s_$b.rpt" "$T/s_$b.out" >/dev/null 2>&1
  for m in "0 0" "1 1" "2 1" "3 1"; do set -- $m
    KWSPLIT=$1 KWLOOP=$2 "$B/kwswmm" "$f" "$T/k_$b.rpt" "$T/k_$b.out" >/dev/null 2>&1; n=$((n+1))
    cmp -s "$T/s_$b.out" "$T/k_$b.out" || { echo "OUT DIFF $b modes $m"; bad=$((bad+1)); }
    diff -q <(grep -av "Analysis begun\|Analysis ended\|Total elapsed" "$T/s_$b.rpt") \
            <(grep -av "Analysis begun\|Analysis ended\|Total elapsed" "$T/k_$b.rpt") >/dev/null \
      || { echo "RPT DIFF $b modes $m"; bad=$((bad+1)); }
  done
done
echo "null gate: $n runs, $bad differences"; rm -rf "$T"; [ $bad -eq 0 ]
