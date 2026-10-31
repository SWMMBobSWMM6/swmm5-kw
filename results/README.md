# results/

Every number in the README, the app and the essay is read from these files.

| File | Written by | What |
|---|---|---|
| `gates.json`, `gates.log` | `tools/gates.py` | every gate on the 13 networks in `models/`, the build's binaries with their SHA-256 |
| `corpus_set.txt` | (from swmm5-rust) | the 3,759 corpus models, relative to the corpus root |
| `interface_models.txt` | (from swmm5-rust) | corpus models that read or write interface files; run one at a time |
| `gate_kwsf.jsonl`, `gate_kwsf.log` | `tools/corpus_gate.py` | KINWAVE and STEADY models, modes 00, 11, 21, 31 |
| `gate_dw.jsonl`, `gate_dw.log` | `tools/corpus_gate.py` | DYNWAVE models (and routing keywords 5.2.4 rejects), mode 11 |
| `gate_iface.jsonl`, `gate_iface.log` | `tools/corpus_gate.py` | interface-file models, modes 00 and 11, one at a time |
| `gate_whatif.jsonl`, `gate_whatif.log` | `tools/corpus_gate.py --force-routing KINWAVE` | the what-if pass: DYNWAVE models copied with routing switched to KINWAVE, mode 11 |
| `whatif_outliers.json` | `tools/trace_outliers.py` | the 30 largest what-if continuity errors, each with stock DYNWAVE's error on the original, the conduits that lost water and a cause |
| `head_fix_check.json` | `tools/head_fix_check.py` | the proposed HEAD overshoot fix against the engine as it stands, on every network the what-if routed |
| `summary.json` | `tools/summarize.py` | the three passes classified: identical, refused by stock and run, stock crashes, different, inconclusive |
| `figdata.json` | `tools/figure_runs.py` | the runs behind every chart in the essay and the flat-channel table (musl builds) |

Each corpus record: `inp`, `routing` (from the file; absent means KINWAVE), `rc_stock`,
`t_stock`, `out_sha` (first 16 hex of the stock `.out`), `stock_errors`, `census` (stock stopped
with ERROR 131 or 133), and per mode `m00`/`m11`/`m21`/`m31`: `rc`, `t`, `out_same`, `rpt_same`
(after removing the wall-clock lines), and for models the extension acted on, its errors,
routing continuity, `swmm_getKwStats` and the report's `KW/SF extension` block. A negative `rc`
is a signal (−11 segmentation fault, −6 abort, −25 the 2 GiB file cap).

Gate runs write interface files into the corpus folders; restore the corpus clone afterwards with
`git checkout . && git clean -fd`.
