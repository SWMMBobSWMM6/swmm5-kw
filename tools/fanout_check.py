#!/usr/bin/env python3
"""Fan-out gate: one junction, many outlets, one of them capped by a flow limit.

  python3 tools/fanout_check.py <build-dir>/kwswmm [--write tests/fanout]

The second outside review of v1.0 (2026-10-31) found that the proportional rules (CAPACITY, AREA)
kept their "this outlet is full" flags in a fixed array of 64, so a capped outlet listed 65th or
later was never marked full: its share was handed out again, part of it was lost at the cap, and
the junction flooded. This gate builds that network at 64, 65, 66 and 130 outlets, moves the capped
outlet through every interesting position, and runs it under all three split rules, KINWAVE and
STEADY. Each run must:
  - allocate exactly what arrives (largest allocation gap under 1e-9 cfs),
  - not flood the junction,
  - give every outlet the same peak flow whatever its position in the file.
"""
import os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outread

def model(n, limited_pos, routing, qlimit=0.1, inflow=20.0):
    """n 12-inch, 400 ft, 1% outlets from J1, each to its own outfall; outlet number limited_pos
    (1-based, by position in [CONDUITS]) has a flow limit. Conduit names never change with position."""
    names = [f'C{k:03d}' for k in range(1, n + 1)]
    lim = 'CLIM'
    order = names[:]                       # CLIM is inserted at limited_pos; the rest keep their order
    order.insert(limited_pos - 1, lim)
    order = order[:n]                      # n outlets in all: CLIM plus n-1 ordinary ones
    L = [f'[TITLE]\nfan-out {n} outlets, limited outlet at position {limited_pos}, {routing}\n',
         '[OPTIONS]', 'FLOW_UNITS CFS', 'INFILTRATION HORTON', f'FLOW_ROUTING {routing}', 'LINK_OFFSETS DEPTH',
         'MIN_SLOPE 0', 'ALLOW_PONDING NO', 'START_DATE 01/01/2026', 'START_TIME 00:00:00',
         'REPORT_START_DATE 01/01/2026', 'REPORT_START_TIME 00:00:00', 'END_DATE 01/01/2026', 'END_TIME 06:00:00',
         'REPORT_STEP 00:05:00', 'WET_STEP 00:01:00', 'DRY_STEP 01:00:00', 'ROUTING_STEP 5', 'THREADS 1', '',
         '[JUNCTIONS]', 'J0 104 8 0 0 0', 'J1 100 8 0 0 0', '', '[OUTFALLS]']
    L += [f'O_{c} 96 FREE NO' for c in order] + ['', '[CONDUITS]', 'CIN J0 J1 400 0.013 0 0 0 0']
    L += [f'{c} J1 O_{c} 400 0.013 0 0 0 {qlimit if c == lim else 0}' for c in order]
    L += ['', '[XSECTIONS]', 'CIN CIRCULAR 4 0 0 0 1'] + [f'{c} CIRCULAR 1 0 0 0 1' for c in order]
    L += ['', '[TIMESERIES]', 'Q1 0:00 0', 'Q1 0:30 ' + str(inflow), 'Q1 5:00 ' + str(inflow), 'Q1 5:30 0', 'Q1 6:00 0',
          '', '[INFLOWS]', 'J0 FLOW Q1 FLOW 1.0 1.0', '', '[REPORT]', 'INPUT NO', 'CONTROLS NO', 'NODES ALL', 'LINKS ALL', '']
    return '\n'.join(L), order

def flooded(rpt):
    return 'No nodes were flooded' not in open(rpt, encoding='latin-1').read()

def link_peaks(out):
    """Peak flow of every link by name, from the binary output (full float precision)."""
    o = outread.read(out)
    return {name: max(o['link'](j, 0)) for j, name in enumerate(o['links'])}

def main():
    exe = sys.argv[1]; write = sys.argv[sys.argv.index('--write') + 1] if '--write' in sys.argv else None
    TD = tempfile.mkdtemp(); fails = 0; runs = 0; worst = 0.0; worst_peak = 0.0
    cases = [(64, (1, 64)), (65, (1, 64, 65)), (66, (1, 65, 66)), (130, (1, 64, 65, 129, 130))]
    for n, positions in cases:
        for routing in ('STEADY', 'KINWAVE'):
            for split in ('2', '3', '1'):
                ref = None; bad = 0
                for pos in positions:
                    txt, order = model(n, pos, routing)
                    fi = os.path.join(TD, 'f.inp'); open(fi, 'w').write(txt)
                    if write and split == '3' and routing == 'STEADY' and n == 65 and pos in (1, 65):
                        open(os.path.join(write, f'fanout65_limited_{pos}.inp'), 'w').write(txt)
                    rpt, out = os.path.join(TD, 'f.rpt'), os.path.join(TD, 'f.out')
                    p = subprocess.run([exe, fi, rpt, out], env={'KWSPLIT': split, 'KWLOOP': '0'}, capture_output=True, text=True)
                    runs += 1
                    imb = float(re.search(r'maxImb=(\S+)', p.stdout).group(1)); worst = max(worst, imb)
                    fl = flooded(rpt); pk = link_peaks(out)
                    if ref is None: ref = pk
                    dev = max(abs(pk[k] - ref[k]) for k in ref)
                    worst_peak = max(worst_peak, dev)
                    ok = imb < 1e-9 and not fl and dev <= 1e-5
                    if not ok:
                        bad += 1; fails += 1
                        print(f'  FAIL n={n} capped outlet at position {pos}, {routing}, split={split}: allocation gap {imb:.6g} cfs, '
                              f'flooded={fl}, largest peak change vs position {positions[0]} {dev:.3g} cfs')
                print(f'n={n:3d} {routing:7s} split={split}: capped outlet at positions {positions}: ' + ('ok' if not bad else f'{bad} failed'))
    print(f'fan-out gate: {runs} runs, {fails} failures, largest allocation gap {worst:.3g} cfs, '
          f'largest change in any outlet peak with the capped outlet moved {worst_peak:.3g} cfs')
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
