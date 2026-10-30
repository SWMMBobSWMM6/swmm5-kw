#!/usr/bin/env python3
"""Summarise the corpus gate records into results/summary.json.

  python3 tools/summarize.py

Reads results/gate_kwsf.jsonl, gate_dw.jsonl, gate_iface.jsonl (whichever exist). The README's
results table, the app's Verify tab and the Doc essay all read summary.json, so they cannot
disagree with each other or with the records.
"""
import json, os, collections
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'results'))

def load(name):
    p = os.path.join(R, name)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

def same(sm): return sm and sm.get('rc') != 'timeout' and sm['out_same'] and sm['rpt_same']

SIGXFSZ = -25   # killed at the 2 GiB file-size cap

def classify(rec, modes):
    rcs = [rec['rc_stock']] + [rec.get('m' + m, {}).get('rc') for m in modes]
    if rec.get('inconclusive') or 'timeout' in rcs or SIGXFSZ in rcs: return 'inconclusive'
    if isinstance(rec['rc_stock'], int) and rec['rc_stock'] < 0:     # stock 5.2.4 itself crashed
        return 'crash_same' if all(r == rec['rc_stock'] for r in rcs) and all(same(rec.get('m' + m)) for m in modes) else 'different'
    if rec['census']:
        on = [rec['m' + m] for m in modes if m != '00' and ('m' + m) in rec]
        off_ok = same(rec.get('m00')) if '00' in modes else True
        ran = all(s.get('rc') == 0 and not s.get('errors') for s in on)
        return 'census_ran' if (ran and off_ok) else 'census_error'
    return 'identical' if all(same(rec.get('m' + m)) for m in modes) else 'different'

passes = [('KINWAVE and STEADY', 'gate_kwsf.jsonl', ['00', '11', '21', '31']),
          ('DYNWAVE (and unrecognised routing)', 'gate_dw.jsonl', ['11']),
          ('Models sharing interface files, run one at a time', 'gate_iface.jsonl', ['00', '11'])]
out = dict(passes=[], census=[], different=[], inconclusive=[])
allinp = set(); maximb = 0.0
for label, fn, modes in passes:
    recs = load(fn)
    if not recs: continue
    c = collections.Counter(); rout = collections.Counter()
    for r in recs:
        k = classify(r, modes); c[k] += 1; rout[r['routing']] += 1; allinp.add(r['inp'])
        if k.startswith('census'):
            on = r.get('m11', {})
            out['census'].append(dict(inp=r['inp'], routing=r['routing'], stock_errors=r['stock_errors'],
                                      result=k, errors=on.get('errors'), continuity=on.get('continuity'),
                                      stats=on.get('stats'), modes={m: dict(rc=r['m' + m]['rc'], continuity=r['m' + m].get('continuity'))
                                                                  for m in modes if m != '00' and ('m' + m) in r}))
            for m in modes:
                st = r.get('m' + m, {}).get('stats')
                if st: maximb = max(maximb, st['maxImb'])
        if k == 'different': out['different'].append(dict(inp=r['inp'], modes={m: r.get('m' + m) for m in modes}))
        if k == 'inconclusive':
            why = r.get('inconclusive') or ('stock and swmm5-kw both reached the 2 GiB file-size cap; the first 2,147,483,648 bytes of their .out files are identical'
                                            if r['rc_stock'] == SIGXFSZ and all(r.get('m' + m, {}).get('out_same') for m in modes) else 'a run hit the time or file-size cap')
            out['inconclusive'].append(dict(inp=r['inp'], why=why))
        if k == 'crash_same': out.setdefault('crashes', []).append(dict(inp=r['inp'], signal=-r['rc_stock']))
    stock_err = sum(1 for r in recs if r['stock_errors'] and not r['census'])
    out['passes'].append(dict(label=label, file=fn, modes=modes, models=len(recs), identical=c['identical'], crash_same=c['crash_same'],
                              census_ran=c['census_ran'], census_error=c['census_error'], different=c['different'],
                              inconclusive=c['inconclusive'], stock_input_errors=stock_err, routing=dict(rout),
                              runs=len(recs) * (1 + len(modes)) - sum(len(modes) for r in recs if r.get('inconclusive'))))
out['models'] = len(allinp)
out['corpus_set'] = sum(1 for l in open(os.path.join(R, 'corpus_set.txt')) if l.strip())
W = load('gate_whatif.jsonl')
if W:
    import statistics
    c = collections.Counter(classify(r, ['11']) for r in W)
    cen = [r for r in W if r['census']]
    ran = [r for r in cen if classify(r, ['11']) == 'census_ran']
    errs = collections.Counter(e for r in cen if classify(r, ['11']) == 'census_error' for e in (r['m11'].get('errors') or ['signal']))
    sp_ = [r['m11']['stats']['split'] for r in ran if r['m11'].get('stats')]; lp_ = [r['m11']['stats']['back'] for r in ran if r['m11'].get('stats')]
    co = [abs(float(r['m11']['continuity'])) for r in ran if r['m11'].get('continuity') not in (None, 'nan', '-nan')]
    for r in ran:
        st = r['m11'].get('stats')
        if st: maximb = max(maximb, st['maxImb'])
    out['whatif'] = dict(file='gate_whatif.jsonl', forced='KINWAVE', models=len(W), census=len(cen), census_ran=c['census_ran'], census_error=c['census_error'],
                         census_error_codes=dict(errs), stock_ran=sum(1 for r in W if not r['census'] and r['rc_stock'] == 0 and not r['stock_errors']),
                         identical=sum(1 for r in W if not r['census'] and r['rc_stock'] == 0 and not r['stock_errors'] and classify(r, ['11']) == 'identical'),
                         stock_other_errors=sum(1 for r in W if not r['census'] and r['stock_errors']),
                         different=c['different'], inconclusive=c['inconclusive'], crash_same=c['crash_same'],
                         split_median=statistics.median(sp_) if sp_ else 0, loop_median=statistics.median(lp_) if lp_ else 0,
                         split_max=int(max(sp_)) if sp_ else 0, loop_max=int(max(lp_)) if lp_ else 0,
                         cont_median_abs=statistics.median(co) if co else 0, cont_over_1=sum(1 for x in co if x > 1),
                         ran=[dict(inp=r['inp'], split=r['m11']['stats']['split'] if r['m11'].get('stats') else None, loops=r['m11']['stats']['back'] if r['m11'].get('stats') else None,
                                   continuity=r['m11'].get('continuity')) for r in ran],
                         different_list=[r['inp'] for r in W if classify(r, ['11']) == 'different'])
    out['max_allocation_imbalance_cfs'] = maximb
    print('whatif', {k: v for k, v in out['whatif'].items() if k not in ('ran', 'different_list')})
out['max_allocation_imbalance_cfs'] = maximb
tot = collections.Counter()
for p in out['passes']:
    for k in ('models', 'identical', 'crash_same', 'census_ran', 'census_error', 'different', 'inconclusive', 'runs', 'stock_input_errors'): tot[k] += p[k]
out['total'] = dict(tot)
json.dump(out, open(os.path.join(R, 'summary.json'), 'w'), indent=1)
for p in out['passes']: print(p['label'], {k: p[k] for k in ('models', 'identical', 'crash_same', 'census_ran', 'census_error', 'different', 'inconclusive', 'runs')})
print('total', dict(tot)); print('census', [(c['inp'], c['result'], c['continuity']) for c in out['census']])
print('different', [d['inp'] for d in out['different']]); print('inconclusive', out['inconclusive'])
