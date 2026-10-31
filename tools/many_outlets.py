#!/usr/bin/env python3
"""A junction with many outlets, one of them flow-limited: the 64/65 boundary test.

  python3 tools/many_outlets.py N POS out.inp [--routing STEADY|KINWAVE] [--limit 0.1] [--peak 20]

Junction J receives a triangular inflow peaking at --peak cfs (0 -> peak over 2 h, back to 0
over 2 h, 6 h run, 1 min reporting). It has N outlet conduits, each 12 in circular, 400 ft at
1% slope, each to its own outfall. Outlet number POS (1-based, in file order) has a MaxFlow of
--limit cfs; the others are unlimited. Built for the review finding of 31 October 2026: in
kwmod.c v1 the CAPACITY/AREA water-filling kept its "capped" flags in char done[64], so a capped
outlet at position 65 or later was never taken out of the share-out, and part of the inflow was
left at the junction. The allocation must not depend on where the limited outlet sits.
"""
import argparse
ap = argparse.ArgumentParser()
ap.add_argument('n', type=int); ap.add_argument('pos', type=int); ap.add_argument('out')
ap.add_argument('--routing', default='STEADY'); ap.add_argument('--limit', type=float, default=0.1)
ap.add_argument('--peak', type=float, default=20.0)
a = ap.parse_args()
assert 1 <= a.pos <= a.n
L = ['[TITLE]', f'{a.n} outlets, outlet {a.pos} limited to {a.limit:g} cfs', '',
     '[OPTIONS]', 'FLOW_UNITS CFS', f'FLOW_ROUTING {a.routing}', 'START_DATE 01/01/2026', 'START_TIME 00:00:00',
     'REPORT_START_DATE 01/01/2026', 'REPORT_START_TIME 00:00:00', 'END_DATE 01/01/2026', 'END_TIME 06:00:00',
     'REPORT_STEP 00:01:00', 'ROUTING_STEP 0:00:30', 'ALLOW_PONDING NO', '',
     '[JUNCTIONS]', ';Name Elev MaxDepth InitDepth SurDepth Aponded', 'J 100 6 0 0 0', '',
     '[OUTFALLS]', ';Name Elev Type']
L += [f'O{k} 96 FREE NO' for k in range(1, a.n + 1)]
L += ['', '[CONDUITS]', ';Name From To Length Roughness InOffset OutOffset InitFlow MaxFlow']
L += [f'C{k} J O{k} 400 0.013 0 0 0 {a.limit if k == a.pos else 0:g}' for k in range(1, a.n + 1)]
L += ['', '[XSECTIONS]', ';Link Shape Geom1 Geom2 Geom3 Geom4 Barrels']
L += [f'C{k} CIRCULAR 1 0 0 0 1' for k in range(1, a.n + 1)]
L += ['', '[INFLOWS]', ';Node Constituent TimeSeries Type Mfactor Sfactor Baseline Pattern', 'J FLOW tri FLOW 1 1', '',
      '[TIMESERIES]', f'tri 0:00 0', f'tri 2:00 {a.peak:g}', f'tri 4:00 0', f'tri 6:00 0', '',
      '[REPORT]', 'INPUT NO', 'CONTROLS NO', 'NODES ALL', 'LINKS ALL', '']
open(a.out, 'w').write('\n'.join(L))
