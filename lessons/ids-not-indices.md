# Break ties by ID, not by position

**What happened.** The first cycle-breaking rule in `toposort.c` chose among tied junctions by
index, which is file order. Shuffling the input file's lines then moved the loop networks'
routing continuity between 0.122% and 0.125%.

**The rule.** Any choice an engine makes among equals must use something that survives
reordering the input: here inflow counts, then `strcmp` on the IDs. `tools/order_check.py`
shuffles `[JUNCTIONS]` and `[CONDUITS]` to hold the line.
