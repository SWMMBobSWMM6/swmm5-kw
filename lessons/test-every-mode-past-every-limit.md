# Test every mode, past every limit you wrote down and every one you didn't

**What happened.** v1's water-filling loop for CAPACITY and AREA kept its "outlet is full" flags in
`char done[64]` and guarded every use with `idx < 64`. The guard kept memory safe and hid the
failure: an outlet past the 64th that hit its cap was clipped and then forgotten, so part of the
junction's inflow stayed behind and flooded it. Nine gates and thousands of corpus runs passed, because
the gates ran CAPACITY and AREA only on five networks with at most three outlets at a junction, and
the corpus what-if pass ran HEAD alone. An outside review found it on 31 October 2026 by building
one junction with 65 outlets and moving the limited outlet from first to last.

**The rule.** For every mode the code offers, run at least one test in that mode on the largest
network the corpus has, not only on the small ones the mode was written for. For every fixed-size
array, write the test that sits one past its size. Then search the code for sizes nobody wrote down
as limits (`[64]`, `< 64`, `MAXOUT`) and treat each one as a limit until a test says otherwise.

**The check that would have caught it.** `tools/gates.py`, "Outlet count and position": one
junction with 63, 64, 65, 66 and 130 outlets and a limited outlet first, 64th, 65th and last,
under all three rules. It fails 16 cases on v1 and passes all 90 runs on v1.1. And the corpus
what-if pass now runs `--modes 11,21,31`.

A constant in the code is a boundary, and a guard around it is a decision about what happens past
it. Either remove the boundary or test both sides of it: 64 and 65, not 2. (From the parallel
review branch's lesson, `claude/kw-v1.1-review-fixes`, whose `tools/fanout_check.py` and
`tests/app/review2.test.js` now run on main.)
