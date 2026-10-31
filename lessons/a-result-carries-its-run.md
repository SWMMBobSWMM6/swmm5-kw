# A result carries its run

**What happened.** The outside review of 31 October 2026 found five ways the page could show a
result that was not what it claimed to be. Results stayed on screen after the model picker changed,
and the CSV export took its file name from the picker, so `diamond_swmm5kw_peaks.csv` held
`split.inp`'s flows. A run stopped after 393 of 43,560 reporting periods still got the green
"swmm5-kw routes it" verdict. A run with no periods exported its peaks as `-Infinity`. A link that
ran backwards all storm showed a peak of 0, because the peak was the signed maximum. And every
hydrograph was drawn one report step early: SWMM stamps its first period at one report step after
the start, and the chart put it at zero.

**The rule.** Every number on screen and in an export carries the run that made it: model name,
settings, time, completion. When the inputs change, the old results say so. Completion decides the
verdict before any comparison is drawn. A missing value is blank, never a sentinel. A flow is
reported with its sign (largest magnitude, plus maximum and minimum where it reverses). Time comes
from the period's own date stamp in the `.out`, not from its index.

**The check.** `tools/app_check.js` replays the reviewer's five scenarios
against `dist/swmm5-kw.html` in Chromium; the in-browser gates on the Verify tab include the
65-outlet case.
