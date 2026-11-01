#!/usr/bin/env python3
"""Outlet census: the most outgoing links any node has, over a list of models.

  python3 tools/outlet_census.py <corpus-root> results/corpus_set.txt

The v1.0 proportional split rules (CAPACITY, AREA) kept per-outlet "full" flags in a char[64], so
they could misallocate only at a junction with more than 64 outlets; at 64 or fewer, v1.0 and v1.1
run the same instructions in the same order. This census says whether any corpus model can tell
the two versions apart. Counts every link section ([CONDUITS] [PUMPS] [ORIFICES] [WEIRS] [OUTLETS]).
"""
import os, sys, json, collections
root, lst = sys.argv[1], sys.argv[2]
LINKS = {'[CONDUITS]', '[PUMPS]', '[ORIFICES]', '[WEIRS]', '[OUTLETS]'}
best = (0, None, None); hist = collections.Counter(); n = 0; missing = 0
for rel in (l.strip() for l in open(lst) if l.strip()):
    p = os.path.join(root, rel)
    if not os.path.exists(p): missing += 1; continue
    n += 1; out = collections.Counter(); name = {}; sec = ''
    for raw in open(p, encoding='latin-1', errors='replace'):
        s = raw.split(';')[0].strip()
        if not s: continue
        if s.startswith('['): sec = s.upper(); continue
        if sec in LINKS:
            f = s.split()
            if len(f) >= 3: out[f[1].upper()] += 1; name.setdefault(f[1].upper(), f[1])   # SWMM IDs ignore case; report the first spelling
    m = max(out.values()) if out else 0
    hist[min(m, 65)] += 1
    if m > best[0]: best = (m, rel, name[max(out, key=out.get)])
res = dict(models=n, missing=missing, max_outlets=best[0], model=best[1], node=best[2],
           over_64=sum(v for k, v in hist.items() if k > 64), with_2_or_more=sum(v for k, v in hist.items() if k >= 2))
print(json.dumps(res))
