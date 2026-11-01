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
| `gate_whatif.jsonl`, `gate_whatif.log` | `tools/corpus_gate.py --force-routing KINWAVE` | the what-if pass: DYNWAVE models copied with routing switched to KINWAVE, modes 11, 21 and 31 (v1: mode 11 only) |
| `whatif_outliers.json` | `tools/trace_outliers.py` | the 30 largest what-if continuity errors, each with stock DYNWAVE's error on the original, the conduits whose volume balance fails worst and a cause |
| `tree_tests.md` | `tools/tree_tests.py` | three outliers made into trees so stock 5.2.4 routes them: stock's continuity error against swmm5-kw's |
| `fanout_fig.json` | `tools/fanout_figure.py` | the 65-outlet junction with the capped outlet in each of 65 positions, AREA, STEADY, on v1 and v1.1 (the Doc's fan-out figure) |
| `outlet_census.json` | `tools/outlet_census.py` | the most outlets any node has in the 3,759-model gate set, and what that means for the 64-outlet defect |
| `app_review2.json` | `tests/app/review2.test.js` | the app's five review findings as 12 browser checks, all passing |
| `version_check.json` | `tools/version_check.py` | v1 against v1.1, HEAD, CAPACITY and AREA, on every network the what-if pass routes |
| `v1/` | the same tools, on engine v1 | the corpus records and `head_fix_check.json` as they stood before v1.1 |
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
