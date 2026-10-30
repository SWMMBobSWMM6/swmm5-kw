# Count crashes apart

**What happened.** The first corpus summary counted the OpenSWMM 2026 code-review decks that
crash EPA 5.2.4 (segmentation faults, aborts) as "identical", because swmm5-kw crashed the same
way and left the same partial output. True, and nearly meaningless: what C does after reading
memory it does not own is undefined, so agreement there proves only that the extension did not
move the crash. One more deck never ends at all (END_TIME of 1e30 hours) and was killed at the
2 GiB file cap.

**The rule.** Keep defined behaviour, crashes and runs that never finished in separate columns
(as swmm5-rust's gate does), so "identical" means what a reader thinks it means.
