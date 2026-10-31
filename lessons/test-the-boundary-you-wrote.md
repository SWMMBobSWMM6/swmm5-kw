# Test the boundary you wrote

**What happened.** The CAPACITY and AREA rules kept their "outlet is full" marks in
`char done[64]`, and every use was guarded with `idx < 64`. The guard kept the array from being
overrun and made the arithmetic wrong: an outlet past the 64th could be capped but never marked,
so it was handed a share again on the next pass and the junction came up short. Every gate passed,
because every shipped junction had two outlets. An outside review built 65 and found it in one run.

**The rule.** A constant in the code is a boundary, and a guard around it is a decision about what
happens past it. Either remove the boundary (here, size the state to the outlet count) or put a
test on both sides of it: 64 and 65, not 2. `tools/fanout_check.py` now runs 64, 65, 66 and 130.
