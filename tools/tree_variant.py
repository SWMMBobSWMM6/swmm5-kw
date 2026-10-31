#!/usr/bin/env python3
"""Make a tree out of a forked network, so stock 5.2.4 will route it under kinematic wave.

  python3 tools/tree_variant.py model.inp out.inp [split-junction ...]

Switches FLOW_ROUTING to KINWAVE, then at each named junction keeps the first outlet conduit in
file order and deletes the others (their [CONDUITS], [XSECTIONS], [LOSSES] and [VERTICES] lines).
The junctions to name are the ones swmm5-kw lists in its report's KW/SF extension block. Used to
test whether a continuity error found with swmm5-kw is the extension's or stock kinematic wave's:
if stock 5.2.4 shows the same error on the tree, the extension did not cause it.
"""
import re, sys
src, dst, splits = sys.argv[1], sys.argv[2], set(s.upper() for s in sys.argv[3:])
lines = open(src, encoding='latin-1').read().split('\n')
sec = ''; first = {}; drop = set()
for raw in lines:
    s = raw.split(';', 1)[0].strip()
    if not s: continue
    if s.startswith('['): sec = s.upper(); continue
    if sec == '[CONDUITS]':
        p = s.split()
        if len(p) >= 3 and p[1].upper() in splits:
            if p[1].upper() in first: drop.add(p[0].upper())
            else: first[p[1].upper()] = p[0]
out = []; sec = ''; seen_route = False
for raw in lines:
    s = raw.split(';', 1)[0].strip()
    if s.startswith('['): sec = s.upper(); out.append(raw); continue
    if sec == '[OPTIONS]' and s.upper().startswith('FLOW_ROUTING'):
        out.append('FLOW_ROUTING         KINWAVE'); seen_route = True; continue
    if s and sec in ('[CONDUITS]', '[XSECTIONS]', '[LOSSES]', '[VERTICES]') and s.split()[0].upper() in drop:
        continue
    out.append(raw)
if not seen_route:
    i = next(k for k, l in enumerate(out) if l.strip().upper() == '[OPTIONS]'); out.insert(i + 1, 'FLOW_ROUTING         KINWAVE')
open(dst, 'w', encoding='latin-1').write('\n'.join(out))
print(f'kept {len(first)} outlets, deleted {len(drop)}: {" ".join(sorted(drop))}')
