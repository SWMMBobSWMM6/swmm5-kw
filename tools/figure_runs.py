#!/usr/bin/env python3
"""Runs behind every chart in the Doc essay. Writes results/figdata.json.

  python3 tools/figure_runs.py <build-dir>

Uses the musl builds (kwswmm-musl, stockseq-musl): the wasm engines in the app match them
byte for byte, so the essay's numbers are the numbers a reader gets in the Run tab.
"""
import json, os, re, struct, subprocess, sys, tempfile, math

R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
B = os.path.abspath(sys.argv[1]); KW = os.path.join(B, 'kwswmm-musl'); ST = os.path.join(B, 'stockseq-musl')
M = os.path.join(R, 'models'); TD = tempfile.mkdtemp()

def read_out(path):
    b = open(path, 'rb').read(); n = len(b); I = lambda o: struct.unpack_from('<i', b, o)[0]
    nsub, nnode, nlink = I(12), I(16), I(20)
    idpos, proppos, outpos, nper = I(n - 24), I(n - 20), I(n - 16), I(n - 12)
    o = idpos; names = []
    for _ in range(nsub + nnode + nlink):
        L = I(o); names.append(b[o + 4:o + 4 + L].decode('latin-1')); o += 4 + L
    links = names[nsub + nnode:]
    o = proppos
    ns = I(o); o += 4 + 4 * ns + 4 * ns * nsub
    nn = I(o); o += 4 + 4 * nn + 4 * nn * nnode
    nl = I(o); o += 4 + 4 * nl + 4 * nl * nlink
    nsv = I(o); o += 4 + 4 * nsv; nnv = I(o); o += 4 + 4 * nnv; nlv = I(o); o += 4 + 4 * nlv; nyv = I(o); o += 4 + 4 * nyv
    step = I(o + 8); rec = 8 + 4 * (nsub * nsv + nnode * nnv + nlink * nlv + nyv)
    def flow(link):
        k = links.index(link); base = 8 + 4 * (nsub * nsv + nnode * nnv + k * nlv)
        return [struct.unpack_from('<f', b, outpos + p * rec + base)[0] for p in range(nper)]
    return links, flow, step

def set_routing(txt, method):
    return re.sub(r'(?m)^FLOW_ROUTING\s+\S+', 'FLOW_ROUTING         ' + method, txt)

def run(exe, txt, split=0, loop=0):
    inp = os.path.join(TD, 'm.inp'); rpt = os.path.join(TD, 'm.rpt'); out = os.path.join(TD, 'm.out')
    open(inp, 'w').write(txt)
    p = subprocess.run([exe, inp, rpt, out], env={'KWSPLIT': str(split), 'KWLOOP': str(loop)}, capture_output=True, text=True)
    r = open(rpt, encoding='latin-1').read()
    m = re.search(r'Flow Routing Continuity.*?Continuity Error \(%\) \.+\s+(\S+)', r, re.S)
    st = re.search(r'rc=(-?\d+) split=(\S+) back=(\S+) allocs=(\S+) maxImb=(\S+) loopSteps=(\S+) meanSweeps=(\S+) maxSweeps=(\S+) nonConv=(\S+) maxRes=(\S+) headIt=(\S+)', p.stdout)
    return dict(cont=float(m.group(1)) if m else None, errs=sorted(set(int(x) for x in re.findall(r'ERROR (\d+)', r))),
                stats=[float(x) for x in st.groups()[1:]] if st else None, out=read_out(out) if not re.search(r'ERROR \d+', r) else None)

def share_at_peak(flow, outs):
    S = [flow(o) for o in outs]; tot = [sum(max(0, s[p]) for s in S) for p in range(len(S[0]))]
    p = max(range(len(tot)), key=lambda i: tot[i])
    return dict(total=tot[p], share=[max(0, s[p]) / tot[p] for s in S], peak=[max(s) for s in S])

fig = {}
# 1. split.inp: shares by rule and routing, and the two outlet hydrographs
sp = open(os.path.join(M, 'split.inp')).read()
cases = [('DYNWAVE (stock)', ST, set_routing(sp, 'DYNWAVE'), 0, 0), ('KINWAVE, HEAD', KW, sp, 1, 1),
         ('STEADY, HEAD', KW, set_routing(sp, 'STEADY'), 1, 1), ('KINWAVE, CAPACITY', KW, sp, 2, 1), ('KINWAVE, AREA', KW, sp, 3, 1)]
fig['split_shares'] = []; series = {}
for name, exe, txt, s, l in cases:
    r = run(exe, txt, s, l); links, flow, step = r['out']
    a = share_at_peak(flow, ['CA', 'CB']); a.update(name=name, cont=r['cont']); fig['split_shares'].append(a)
    if name in ('DYNWAVE (stock)', 'KINWAVE, HEAD'): series[name] = dict(CA=flow('CA'), CB=flow('CB'), C1=flow('C1'), step=step)
fig['split_series'] = series
fig['split_stock_kw'] = run(ST, sp)['errs']

# 2. every link peak in the five split and loop networks, KINWAVE HEAD against DYNWAVE
fig['peaks'] = []
for name in ('split', 'diamond', 'braid', 'loopactive', 'loop'):
    txt = open(os.path.join(M, name + '.inp')).read()
    k = run(KW, txt, 1, 1); d = run(ST, set_routing(txt, 'DYNWAVE'))
    kl, kf, _ = k['out']; dl, df, _ = d['out']
    for L in kl:
        fig['peaks'].append(dict(model=name, link=L, kw=max(kf(L)), dw=max(df(L))))
    fig.setdefault('nets', {})[name] = dict(kw_cont=k['cont'], dw_cont=d['cont'], stats=k['stats'],
                                             stock_errs=run(ST, txt)['errs'])

# 3. the relief loop: R1 under KW HEAD and DYNWAVE
la = open(os.path.join(M, 'loopactive.inp')).read()
k = run(KW, la, 1, 1); d = run(ST, set_routing(la, 'DYNWAVE'))
fig['loop_series'] = dict(kw=k['out'][1]('R1'), dw=d['out'][1]('R1'), step=k['out'][2], kw_stats=k['stats'])

# 4. stock KW continuity on a plain chain, inflow swept through full capacity
ch = open(os.path.join(M, 'chain30.inp')).read()
fig['chain_sweep'] = []
q = 20.0
while q <= 46.0001:
    txt = re.sub(r'(?m)^Q1 (0:30|3:00) 30$', lambda m: 'Q1 %s %g' % (m.group(1), q), ch)
    fig['chain_sweep'].append(dict(q=q, musl=run(ST, txt)['cont']))
    q += 0.5

# 5. circular section factor, analytic: S(y)/S_full with S = A R^(2/3)
def S(t):   # t = central angle
    A = (t - math.sin(t)) / 8.0; P = t / 2.0; return A * (A / P) ** (2.0 / 3.0) if P > 0 else 0.0
Sf = S(2 * math.pi); curve = []
for i in range(0, 101):
    y = i / 100.0; t = 2 * math.acos(max(-1.0, min(1.0, 1 - 2 * y))); curve.append([y, S(t) / Sf])
fig['section_factor'] = curve

json.dump(fig, open(os.path.join(R, 'results', 'figdata.json'), 'w'), separators=(',', ':'))
print('wrote results/figdata.json:', ', '.join(fig))
print('split shares:', [(c['name'], [round(100 * x, 1) for x in c['share']], c['cont']) for c in fig['split_shares']])
print('chain sweep max |cont|:', max(fig['chain_sweep'], key=lambda c: abs(c['musl'] or 0)))
