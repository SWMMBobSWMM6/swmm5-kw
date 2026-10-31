# Tree tests: is a continuity error the extension's or stock kinematic wave's?

Made by `python3 tools/tree_tests.py <kwbal> <corpus> results/tree_tests.md` against the corpus at 9ee63bd;
`<kwbal>` is built by `tools/conduit_balance.sh`. "Forks in place" is the model switched to KINWAVE and run
with HEAD + loops. "Tree" is the same copy with all but the first outlet deleted at each split junction
(`tools/tree_variant.py`) and run with the extension off, which is stock 5.2.4. A negative continuity error
means the run reports more water leaving than entered. Conduit imbalance is the sum over the run of
(inflow − outflow)·Δt − ΔV; negative means the conduit passed on more than it was given.

| Model (switched to KINWAVE) | Split junctions | swmm5-kw, forks in place | Stock 5.2.4, tree | Worst conduits in the tree run (imbalance, steps at full capacity) | WARNING 04 lines |
|---|---|---|---|---|---|
| `XPSWMM/ATTEN.inp` | A, B (218 219 deleted) | -20.955% | -21.856% | `Aout` -20,003 ft³, 0 | 7 |
| `XPSWMM/UPWSH1.inp` | 102 (C_OUT_SYNTH deleted) | -10,066.240% | -10,069.031% | `DCH_HU` -39,623,348 ft³, 4,320; `DCH_FF` -11,247,987 ft³, 4,320; `DCH_HL` -4,990,051 ft³, 0 | 18 |
| `NCIMM_ROUTING/river.inp` | G143 (BOX PIPE deleted) | -62.264% | -63.368% | `L15` -3,381,613 ft³, 850; `L16` -5,639 ft³, 0; `L7` -3,647 ft³, 0 | 4 |

In each case stock's error on the tree is as large as swmm5-kw's with the forks in place, or larger.
