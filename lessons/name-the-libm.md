# Name the maths library

**What happened.** The wasm engine and a native glibc build of the same source gave different
kinematic-wave results after 241 minutes of a storm. Neither was wrong: wasi-libc's maths is
musl's, and musl and glibc round some functions differently in the last bit, which kinematic
wave's root-finding amplifies to about 2% on a recession. Dynamic wave and steady flow were
identical under both libraries.

**The rule.** A claim that two kinematic-wave runs come from the same engine says which `libm`.
The wasm gate compares against a native **musl** build, and figures quoted for the browser come
from musl builds.
