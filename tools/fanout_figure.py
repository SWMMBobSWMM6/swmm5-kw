#!/usr/bin/env python3
"""Data for the Doc's fan-out figure: 65 outlets, AREA rule, STEADY routing, the capped outlet moved
through every position, run on two engine builds (v1.0 and v1.1). Writes results/fanout_fig.json.

  python3 tools/fanout_figure.py <v1.0 kwswmm> <v1.1 kwswmm>
"""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fanout_check, outread
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TD = tempfile.mkdtemp(); out = dict(n=65, rule='AREA', routing='STEADY', qlimit=0.1, inflow=20.0, positions=list(range(1, 66)), runs={})
for label, exe in (('v1.0', sys.argv[1]), ('v1.1', sys.argv[2])):
    gaps, flood = [], []
    for pos in out['positions']:
        txt, _ = fanout_check.model(65, pos, 'STEADY')
        fi, rpt, o = os.path.join(TD, 'f.inp'), os.path.join(TD, 'f.rpt'), os.path.join(TD, 'f.out')
        open(fi, 'w').write(txt)
        p = subprocess.run([exe, fi, rpt, o], env={'KWSPLIT': '3', 'KWLOOP': '0'}, capture_output=True, text=True)
        gaps.append(float(re.search(r'maxImb=(\S+)', p.stdout).group(1)))
        O = outread.read(o); j1 = O['nodes'].index('J1')
        flood.append(max(O['node'](j1, 5)))           # peak flooding at the junction, cfs
    out['runs'][label] = dict(gap=gaps, flood=flood)
    print(label, 'largest gap', max(gaps), 'at position', gaps.index(max(gaps)) + 1, 'peak flooding', max(flood))
json.dump(out, open(os.path.join(R, 'results', 'fanout_fig.json'), 'w'), indent=1)
