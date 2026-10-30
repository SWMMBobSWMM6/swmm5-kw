//-----------------------------------------------------------------------------
//   kwmod.c
//
//   Kinematic Wave / Steady Flow extensions for EPA SWMM 5.2.4:
//     (1) node bifurcations: a junction may have several conduit outlets;
//         its outflow is allocated among them once per sweep
//     (2) directed loops: links that close a cycle are routed with a
//         per-time-step fixed-point iteration (see flowrout.c)
//
//   Both features are OFF by default (KwSplitMode = KwLoopMode = 0), in which
//   case the engine behaves exactly like stock 5.2.4 (ERROR 133 / ERROR 131).
//
//   Split modes:
//     0 STOCK     ERROR 133 at any junction with more than one outlet
//     1 HEAD      common allocation head: find y with sum_k Q_k(y) = Q, where
//                 Q_k(y) = min(cap_k, barrels*beta*S(A(y - offset_k)))
//     2 CAPACITY  proportional to cap_k = barrels*min(qFull, qLimit)
//     3 AREA      proportional to barrels * upstream flow area of the previous
//                 step (falls back to CAPACITY when every area is zero)
//   Every mode caps each branch at cap_k; inflow beyond sum(cap_k) stays at
//   the node, exactly as the KW/SF conduit solvers already clip it.
//-----------------------------------------------------------------------------
#define _CRT_SECURE_NO_DEPRECATE
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "headers.h"

int     KwSplitMode = 0;          // 0 stock, 1 head, 2 capacity, 3 area
int     KwLoopMode  = 0;          // 0 stock (ERROR 131), 1 iterate
char*   KwBackEdge  = NULL;       // per link: closes a directed cycle
int     KwBackEdgeCount = 0;
int     KwSplitNodeCount = 0;
long    KwStamp = 0;              // incremented once per routing sweep

static char*   SplitNode  = NULL; // per node: allocation active
static int*    OutStart   = NULL; // CSR of conduit outlets per node
static int*    OutList    = NULL;
static long*   AllocStamp = NULL; // per node: sweep stamp of cached allocation
static double* AllocQ     = NULL; // per link: allocated inflow (cfs)

// --- run statistics (exposed through swmm_getKwStats)
static double StatAllocs, StatMaxImbalance, StatLoopSteps, StatSweeps,
              StatMaxSweeps, StatNonConv, StatMaxResidual, StatHeadIters;

static double branchCap(int L)
{
    int k = Link[L].subIndex;
    double cap = Link[L].qFull * Conduit[k].barrels;
    if ( Link[L].qLimit > 0.0 ) cap = MIN(cap, Link[L].qLimit);
    if ( Link[L].setting == 0.0 ) cap = 0.0;          // closed conduit
    return MAX(cap, 0.0);
}

static double branchQ(int L, double y, double cap)
{
    int k = Link[L].subIndex;
    double h = y - Link[L].offset1, a, q;
    if ( cap <= 0.0 || h <= 0.0 ) return 0.0;
    if ( h >= Link[L].xsect.yFull ) return cap;
    a = xsect_getAofY(&Link[L].xsect, h);
    q = Conduit[k].barrels * Conduit[k].beta * xsect_getSofA(&Link[L].xsect, a);
    return MIN(q, cap);
}

int kwmod_init(void)
//  Called from toposort_sortLinks (KW/SF only) after the adjacency is known.
{
    int i, j, n;
    kwmod_close();
    StatAllocs = StatMaxImbalance = StatLoopSteps = StatSweeps = 0.0;
    StatMaxSweeps = StatNonConv = StatMaxResidual = StatHeadIters = 0.0;
    KwBackEdgeCount = 0;
    KwSplitNodeCount = 0;
    KwStamp = 0;
    n = Nobjects[NODE];
    SplitNode  = (char*)  calloc(n + 1, sizeof(char));
    OutStart   = (int*)   calloc(n + 1, sizeof(int));
    AllocStamp = (long*)  calloc(n + 1, sizeof(long));
    OutList    = (int*)   calloc(Nobjects[LINK] + 1, sizeof(int));
    AllocQ     = (double*)calloc(Nobjects[LINK] + 1, sizeof(double));
    KwBackEdge = (char*)  calloc(Nobjects[LINK] + 1, sizeof(char));
    if ( !SplitNode || !OutStart || !AllocStamp || !OutList || !AllocQ || !KwBackEdge )
        return 0;
    for ( j = 0; j < Nobjects[LINK]; j++ ) OutStart[Link[j].node1 + 1]++;
    for ( i = 0; i < n; i++ ) OutStart[i + 1] += OutStart[i];
    {
        int* fill = (int*)calloc(n + 1, sizeof(int));
        if ( !fill ) return 0;
        for ( j = 0; j < Nobjects[LINK]; j++ )
        {
            i = Link[j].node1;
            OutList[OutStart[i] + fill[i]] = j;
            fill[i]++;
        }
        free(fill);
    }
    for ( i = 0; i < n; i++ ) AllocStamp[i] = -1;
    return 1;
}

void kwmod_close(void)
{
    FREE(SplitNode); FREE(OutStart); FREE(OutList);
    FREE(AllocStamp); FREE(AllocQ); FREE(KwBackEdge);
}

int kwmod_canSplit(int node)
//  A junction can split if split mode is on and every outlet is a real conduit.
{
    int m, L;
    if ( KwSplitMode == 0 || !SplitNode ) return 0;
    if ( Node[node].type == STORAGE || Node[node].type == DIVIDER ||
         Node[node].type == OUTFALL ) return 0;
    for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
    {
        L = OutList[m];
        if ( Link[L].type != CONDUIT ) return 0;
        if ( Link[L].xsect.type == DUMMY ) return 0;
    }
    return 1;
}

void kwmod_markSplitNode(int node)
{
    if ( SplitNode && !SplitNode[node] ) { SplitNode[node] = 1; KwSplitNodeCount++; }
}

int kwmod_isSplitNode(int node)
{
    return SplitNode ? SplitNode[node] : 0;
}

static void allocate(int node)
{
    int m, L, iter, nOut = OutStart[node + 1] - OutStart[node];
    double qT = Node[node].inflow + Node[node].overflow;
    double capSum = 0.0, sum, y0, y1, y, f;
    double w, wSum, remaining;

    for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
    {
        L = OutList[m];
        AllocQ[L] = 0.0;
        capSum += branchCap(L);
    }
    StatAllocs += 1.0;
    if ( qT <= 0.0 || capSum <= 0.0 || nOut == 0 ) return;

    // --- everything full: each branch takes its cap, excess stays at node
    if ( qT >= capSum )
    {
        for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
        {
            L = OutList[m];
            AllocQ[L] = branchCap(L);
        }
        return;
    }

    if ( KwSplitMode == 1 )
    {
        // --- common allocation head by bisection on a monotone function
        y0 = 0.0; y1 = 0.0;
        for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
        {
            L = OutList[m];
            y1 = MAX(y1, Link[L].offset1 + Link[L].xsect.yFull);
        }
        y = 0.5 * (y0 + y1);
        for ( iter = 0; iter < 80; iter++ )
        {
            y = 0.5 * (y0 + y1);
            sum = 0.0;
            for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
            {
                L = OutList[m];
                sum += branchQ(L, y, branchCap(L));
            }
            f = sum - qT;
            if ( fabs(f) <= 1.0e-10 * capSum ) break;
            if ( f > 0.0 ) y1 = y; else y0 = y;
        }
        StatHeadIters += (double)(iter + 1);
        // --- close the tiny bisection residual exactly on the branches that
        //     are below their cap; a capped branch keeps exactly its cap, so
        //     the KW solver still sees it as running full (a scaled 0.9999999
        //     of qFull would flip its inlet area to the lower root of S(A))
        {
            double sumFree = 0.0, sumCapped = 0.0, cap;
            for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
            {
                L = OutList[m];
                cap = branchCap(L);
                AllocQ[L] = branchQ(L, y, cap);
                if ( AllocQ[L] >= cap ) sumCapped += AllocQ[L];
                else sumFree += AllocQ[L];
            }
            if ( sumFree > 0.0 && qT > sumCapped )
            {
                for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
                {
                    L = OutList[m];
                    if ( AllocQ[L] < branchCap(L) )
                        AllocQ[L] = MIN(AllocQ[L] * (qT - sumCapped) / sumFree, branchCap(L));
                }
            }
            else if ( sumFree + sumCapped <= 0.0 )
                for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
                {   L = OutList[m]; AllocQ[L] = qT * branchCap(L) / capSum; }
        }
    }
    else
    {
        // --- proportional (CAPACITY or AREA) with water-filling at the caps
        char done[64];
        int  useArea = (KwSplitMode == 3);
        remaining = qT;
        memset(done, 0, sizeof(done));
        if ( useArea )
        {
            wSum = 0.0;
            for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
            {
                L = OutList[m];
                if ( branchCap(L) > 0.0 )
                    wSum += Conduit[Link[L].subIndex].a1 * Conduit[Link[L].subIndex].barrels;
            }
            if ( wSum <= 0.0 ) useArea = 0;   // cold start: fall back to capacity
        }
        for ( iter = 0; iter < nOut + 1 && remaining > 0.0; iter++ )
        {
            int capped = 0;
            wSum = 0.0;
            for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
            {
                int idx = m - OutStart[node];
                L = OutList[m];
                if ( idx < 64 && done[idx] ) continue;
                w = useArea ? Conduit[Link[L].subIndex].a1 * Conduit[Link[L].subIndex].barrels
                            : branchCap(L);
                if ( branchCap(L) <= 0.0 ) w = 0.0;
                wSum += w;
            }
            if ( wSum <= 0.0 ) break;
            for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
            {
                int idx = m - OutStart[node];
                double cap;
                L = OutList[m];
                if ( idx < 64 && done[idx] ) continue;
                w = useArea ? Conduit[Link[L].subIndex].a1 * Conduit[Link[L].subIndex].barrels
                            : branchCap(L);
                cap = branchCap(L);
                if ( cap <= 0.0 ) w = 0.0;
                AllocQ[L] = remaining * w / wSum;
                if ( AllocQ[L] > cap ) { AllocQ[L] = cap; if ( idx < 64 ) done[idx] = 1; capped = 1; }
            }
            if ( !capped ) break;
            // --- recompute what is left for the uncapped branches
            remaining = qT;
            for ( m = OutStart[node]; m < OutStart[node + 1]; m++ )
            {
                int idx = m - OutStart[node];
                if ( idx < 64 && done[idx] ) remaining -= AllocQ[OutList[m]];
            }
        }
    }

    // --- conservation check (always on): allocations never create water
    sum = 0.0;
    for ( m = OutStart[node]; m < OutStart[node + 1]; m++ ) sum += AllocQ[OutList[m]];
    f = fabs(sum - MIN(qT, capSum));
    if ( f > StatMaxImbalance ) StatMaxImbalance = f;
}

double kwmod_getOutflow(int node, int link)
//  Replaces Node[].inflow + Node[].overflow for split junctions: returns the
//  share of the node's outflow allocated to this outlet link. All shares are
//  computed together at the first outlet touched in a sweep, so the result
//  does not depend on which outlet is evaluated first.
{
    if ( AllocStamp[node] != KwStamp )
    {
        allocate(node);
        AllocStamp[node] = KwStamp;
    }
    return AllocQ[link];
}

void kwmod_noteLoopStep(int sweeps, double residual, int converged)
{
    StatLoopSteps += 1.0;
    StatSweeps += sweeps;
    if ( sweeps > StatMaxSweeps ) StatMaxSweeps = sweeps;
    if ( !converged ) StatNonConv += 1.0;
    if ( residual > StatMaxResidual ) StatMaxResidual = residual;
}

void kwmod_getStats(double* v)
//  v[0] split nodes, v[1] back-edge links, v[2] allocations made,
//  v[3] max allocation imbalance (cfs), v[4] steps iterated for loops,
//  v[5] mean sweeps per iterated step, v[6] max sweeps, v[7] steps that hit
//  the sweep cap, v[8] max final loop residual (cfs), v[9] mean head iterations
{
    v[0] = KwSplitNodeCount;
    v[1] = KwBackEdgeCount;
    v[2] = StatAllocs;
    v[3] = StatMaxImbalance;
    v[4] = StatLoopSteps;
    v[5] = StatLoopSteps > 0 ? StatSweeps / StatLoopSteps : 0.0;
    v[6] = StatMaxSweeps;
    v[7] = StatNonConv;
    v[8] = StatMaxResidual;
    v[9] = StatAllocs > 0 ? StatHeadIters / StatAllocs : 0.0;
}
