# Look at the sign, not just the size

**What happened.** In September the relief loop's pipe R1 was reported as carrying 0.51 cfs under
swmm5-kw and 3.34 cfs under dynamic wave, and both were called recirculation. The comparison
took the largest absolute flow from each run. Under dynamic wave R1's flow is negative for the
whole storm: the pipe runs backwards, J1 → J3, as a second path downstream. Kinematic wave cannot
reverse a link, so the two numbers describe water going opposite ways.

**What caught it.** Plotting both series on one axis for the essay (`results/figdata.json`,
`loop_series`). The minimum of the dynamic-wave series is −3.34; its maximum is 0.

**The rule.** When two engines are compared on a link, compare signed series, or at least
the signed extremes, before comparing magnitudes. A peak taken as `max(abs(q))` hides a reversal.
