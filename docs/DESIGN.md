# Design and code map

Base: EPA SWMM 5.2.4, tag `v5.2.4`, commit 7952ca8 (this repository's first commit, `4cbd1eb`).
The extension is the diff from `4cbd1eb` to `5c6c060`, also kept as
[`patch/swmm524-kw.patch`](../patch/swmm524-kw.patch): seven files, 622 lines added (587 not blank), 4 removed.

## Why stock SWMM needs a tree

Kinematic wave and steady flow route a step in one pass, upstream to downstream. Each link takes
its inflow from its upstream node, routes it, and hands its outflow to its downstream node. For
that pass to exist, every node must know its whole inflow before any of its outlets are routed,
and a node must have only one place to send its water. So `flowrout.c` checks the layout first:

* a junction with two or more outlets stops the run with **ERROR 133**;
* a directed cycle (the water can come back to where it started) stops the sort in `toposort.c`
  with **ERROR 131**.

Dynamic wave solves heads at every node together, so it has neither restriction and this
extension never touches it.

## Files touched

| File | What changed | Where to look |
|---|---|---|
| `kwmod.c` (new) | globals `KwSplitMode`, `KwLoopMode`, `KwBackEdge[]`, `KwBackEdgeCount`, `KwSplitNodeCount`, `KwStamp`; CSR outlet lists; allocator; run statistics | `allocate()`, `kwmod_getOutflow()` |
| `flowrout.c` | `validateTreeLayout` marks split junctions instead of raising ERROR 133; `flowrout_execute` bumps `KwStamp` and branches to `kwLoopExecute` when loops exist; report block in `flowrout_init`; loop summary line in `flowrout_close`; `kwListIDs` | end of file |
| `toposort.c` | `toposort_sortLinks` calls `kwmod_init`; `topoSort` breaks cycles and flags loop-closing links when `KwLoopMode` is on | `topoSort()` |
| `node.c` | `node_getOutflow`, default branch: `if ( kwmod_isSplitNode(j) ) return kwmod_getOutflow(j, k);` | one line |
| `swmm5.c`, `include/swmm5.h` | `swmm_setKwOptions`, `swmm_getKwStats` | end of `swmm5.c` |
| `funcs.h` | declarations for everything in `kwmod.c` | before "Flow/Quality Routing Methods" |

`kwmod_init` runs from `toposort_sortLinks` on the KW/SF path only, so dynamic wave never
allocates or touches any of it. `kwmod_close` runs from `flowrout_close`. EPA's CMake globs
`src/solver/*.c`, so `kwmod.c` is built with no CMake change.

## API

```c
int swmm_setKwOptions(int splitMode, int loopMode);  // before swmm_start
    // splitMode: 0 stock (ERROR 133), 1 HEAD, 2 CAPACITY, 3 AREA
    // loopMode:  0 stock (ERROR 131), 1 iterate
int swmm_getKwStats(double v[10]);                    // after swmm_end
    // v[0] split junctions      v[1] loop-closing links   v[2] allocations
    // v[3] max allocation imbalance (cfs)                 v[4] steps iterated
    // v[5] mean sweeps          v[6] max sweeps           v[7] steps at the 60-sweep cap
    // v[8] max final loop residual (cfs)                  v[9] mean HEAD bisection iterations
```

Both are exported with EPA's `DLLEXPORT` macro, like the rest of `swmm5.h`. EPA's optional
`BUILD_DEF=ON` build (the legacy 32-bit `bindings/swmm5.def`) does not list them; nobody has
built that variant with the extension.

## Which junctions split

`kwmod_canSplit(node)`: split mode on, node is not STORAGE, DIVIDER or OUTFALL, and every
outlet (links with `node1 == node`, counted as SWMM's directed adjacency counts them) is a
CONDUIT whose cross-section is not DUMMY. Otherwise ERROR 133 is raised exactly as stock.
Relaxing 133 does not relax 131, 115 (adverse slope), 135, 139 (regulator not leaving storage)
or 141.

## Allocation (`allocate(node)`)

- Target `qT = Node.inflow + Node.overflow`: the quantity stock hands a single outlet.
- `cap_k = Qfull·barrels`, reduced to `qLimit` when set, 0 when the conduit's setting is 0
  (conduit settings are binary under KW/SF in SWMM5).
- `qT ≥ Σcap`: every outlet gets exactly its cap; the excess stays at the node and becomes
  ponding or flooding through the stock node update, as it does for one full pipe.
- **HEAD** (mode 1): bisection on y ∈ [0, max(offset_k + yFull_k)] for
  `Σ min(cap_k, barrels·β·S(A(y − offset_k))) = qT`, stopping at |f| ≤ 1e-10·Σcap or
  80 iterations (22 to 31 is typical). The cap keeps the sum monotone: for a circular pipe
  S(A)/S_full passes 1 at y/D = 0.820 and peaks at 1.076 at y/D = 0.938. The last residual is
  spread only over outlets **below** their cap.
- **CAPACITY** (mode 2): in proportion to `cap_k`, water-filled (an outlet that reaches its cap
  is removed and the rest redistributed).
- **AREA** (mode 3): in proportion to `barrels·Conduit.a1` from the previous step, water-filled;
  falls back to CAPACITY when every weight is zero (the cold start).
- All outlets of a node are computed together at the first request in a sweep and cached under
  `KwStamp`. The stamp moves every sweep, so a loop's re-sweep sees new inflows, and the result
  never depends on which outlet asks first.
- A permanent check keeps the largest `|Σ alloc − min(qT, Σcap)|` (statistic v[3]).

HEAD is an allocation rule at normal depth, not a water surface: it carries no backwater and
no surcharge.

## Loops

**Sort (`topoSort`).** Stock Kahn's algorithm until the stack empties with links left. Then
force the unfinished node with outlets that has the fewest unsorted inflow links; ties go to the
node with the most inflow links already sorted (the cycle's entry), then to the smallest ID by
`strcmp`, so file order never decides. After sorting, a link is loop-closing when its downstream
node was popped no later than its upstream node and is not an outfall. With `KwLoopMode` 0 the
sort is stock and a cycle still raises ERROR 131.

**Step (`kwLoopExecute`).**
1. Snapshot node `inflow, outflow, overflow, newVolume, newDepth, updated`, the whole
   `Conduit[]` array (`Nlinks[CONDUIT]` entries) and every `Link.newFlow`.
2. Guess each loop-closing link's outflow as `max(Link.newFlow, 0)` from the previous step and
   add the guess to its downstream node's inflow.
3. Stock sweep in sorted order (`updateStorageState`, `getLinkInflow`, kinwave or steady flow),
   except that a loop-closing link's routed outflow is recorded instead of added to its node.
4. Converged when every |routed − guess| ≤ FLOW_TOL (1e-5 cfs) + 1e-6·(largest loop-link flow).
   Otherwise restore the snapshot, take routed as the new guess (blended 0.5 from sweep 20) and
   sweep again, at most 60 times (`KW_MAXSWEEP`).
5. Book `routed − guess` to each receiving node, then stock `setNewNodeState` and
   `setNewLinkState`. Continuity is exact whether or not the iteration converged.

The snapshot is what makes kinematic wave sound here: a KW conduit carries the step's starting
`q1, q2, a1, a2`, and every trial sweep must start from them. Steady flow has no memory.

## Report additions

Only when the run has split junctions or loop links, so every other run's report is
byte-identical to stock:

```
  *******************************************
  KW/SF extension (modified engine, kwmod.c)
  *******************************************
  Multi-outlet junctions ... 1  (allocation HEAD)
    J3
  Loop-closing links ....... 1  (iterated each step)
    R1

  Loop iteration: 4320 steps, mean 2.28 sweeps, max 60, 73 steps at the 60-sweep cap, max residual 0.3628 CFS
```

The report header still says Build 5.2.4 (see [DECISIONS.md](DECISIONS.md)).

## Open defect: HEAD can hand out slightly more than arrived

Found on 31 October 2026 by the corpus what-if pass (`docs/VERIFICATION.md`), on
`XPSWMM/EXTUT17.inp` switched to KINWAVE. Junction `inflow` has two outlets: conduit `37`, a 1 ft
pipe with a full-flow capacity of 0.1126658 cfs, and `supernever`, a trapezoidal overflow channel
whose invert is 100 ft up, with 14,812 cfs of capacity. At one step 0.1126642 cfs arrived, just
under pipe 37's capacity. The bisection stops when

```c
if ( fabs(f) <= 1.0e-10 * capSum ) break;
```

and with `capSum` = 14,812 cfs that tolerance is 1.48e-6 cfs, coarser than the gap between the
inflow and pipe 37's capacity. The bisection stopped just past that capacity, pipe 37 was capped
at 0.1126658 cfs, and the correction that follows only rescales outlets below their caps:

```c
if ( AllocQ[L] >= cap ) sumCapped += AllocQ[L];
else sumFree += AllocQ[L];
...
if ( sumFree > 0.0 && qT > sumCapped )
```

Here `sumCapped` > `qT`, so no branch ran and the junction handed out 1.48e-6 cfs more than it
had. The same thing happened in other corpus networks; `results/head_fix_check.json` lists every
one. None of the shipped test networks reaches it (largest gap 7.1e-15 cfs).

`patch/kw-v1.1-head-overshoot.patch` adds one branch after that test: when the capped outlets
alone exceed what arrived, scale every outlet down to it, which can never break a cap. It brings
EXTUT17's largest gap to 1.4e-17 cfs and leaves all 52 runs on `models/` byte-identical. It is
**not applied**: the engine in `src/` is the one Bob's apps already embed, and changing it is
his call ([DECISIONS.md](DECISIONS.md)).

## Bugs caught while building (keep them fixed in any port)

The HEAD residual used to be spread over every outlet:

```c
if ( sum > 0.0 )
    for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
        AllocQ[OutList[m]] *= qT / sum;
```

That nudged a capped outlet to 0.9999999·Qfull, which flips KW's inlet area from full to the
lower root of S(A), about 18% of full area. Now only outlets below their cap take the correction.

The loop snapshot was first written as

```c
memcpy(sCond, Conduit, Nobjects[CONDUIT] * sizeof(TConduit))
```

`Nobjects` is indexed by object type, not link subtype, so it would have copied the rain gage
count. It must be `Nlinks[CONDUIT]`. Caught before it ran.

The cycle tie-break first used node index, so the forced node depended on file order and the
loop models' continuity moved with it (0.122% against 0.125%). It now uses inflow counts, then
`strcmp` on IDs.

The first JavaScript driver skipped `swmm_end` after a failed `swmm_start`:

```js
try { if (started) { ex.swmm_end(); ...
```

That left a truncated `.out` on ERROR 133 and 131 runs (390 bytes against 414).
`wasm/kwengine.js` now mirrors `swmm_run`: end and report whenever open succeeded.
