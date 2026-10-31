"""Figures for the Doc essay, drawn once and rendered twice.

Each function takes a palette P and returns an SVG string. The app passes CSS custom
properties (so the figure follows the theme); the .docx build passes light-theme hex colours
and rasterises the result. Colours go in style attributes, because SVG presentation
attributes do not accept var().
"""
import json, math, os

APP = dict(ink='var(--f-ink)', dim='var(--f-dim)', line='var(--f-line)', face='var(--f-face)', soft='var(--f-soft)',
           a='var(--f-a)', b='var(--f-b)', c='var(--f-c)', d='var(--f-d)', e='var(--f-e)', f='var(--f-f)',
           kw='var(--kw)', epa='var(--epa)', dw='var(--dw)', on='var(--f-on)')
DOCX = dict(ink='#1b2733', dim='#5a6878', line='#cfd8e3', face='#ffffff', soft='#eef3f8',
            a='#1f6fd1', b='#a15c00', c='#15803d', d='#b91c1c', e='#7e22ce', f='#0f766e',
            kw='#0f766e', epa='#a15c00', dw='#7e22ce', on='#ffffff')
FONT = "font-family:'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif"


def _svg(w, h, body, label):
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}" '
            f'style="{FONT}">{body}</svg>')


def T(x, y, s, P, size=12, col='ink', anchor='start', weight=400, extra=''):
    return (f'<text x="{x:.1f}" y="{y:.1f}" style="fill:{P[col]};font-size:{size}px;font-weight:{weight}" '
            f'text-anchor="{anchor}" {extra}>{s}</text>')


def line(x1, y1, x2, y2, P, col='line', w=1.0, dash=None):
    d = f';stroke-dasharray:{dash}' if dash else ''
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" style="stroke:{P[col]};stroke-width:{w}{d}"/>'


def path(d, P, col, w=2.0, fill='none', dash=None, op=1.0):
    f = P[fill] if fill in P else fill
    dd = f';stroke-dasharray:{dash}' if dash else ''
    return f'<path d="{d}" style="stroke:{P[col] if col in P else col};stroke-width:{w};fill:{f};opacity:{op}{dd}" stroke-linejoin="round" stroke-linecap="round"/>'


def rect(x, y, w, h, P, fill='soft', stroke='line', r=6, sw=1.0):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" style="fill:{P[fill]};stroke:{P[stroke]};stroke-width:{sw}"/>'


def circle(x, y, r, P, fill='face', stroke='ink', sw=1.6):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" style="fill:{P[fill]};stroke:{P[stroke]};stroke-width:{sw}"/>'


def arrow(x1, y1, x2, y2, P, col='ink', w=1.8, dash=None, head=7):
    ang = math.atan2(y2 - y1, x2 - x1)
    hx1 = x2 - head * math.cos(ang - 0.42); hy1 = y2 - head * math.sin(ang - 0.42)
    hx2 = x2 - head * math.cos(ang + 0.42); hy2 = y2 - head * math.sin(ang + 0.42)
    return (line(x1, y1, x2 - 0.6 * head * math.cos(ang), y2 - 0.6 * head * math.sin(ang), P, col, w, dash) +
            f'<path d="M{x2:.1f} {y2:.1f}L{hx1:.1f} {hy1:.1f}L{hx2:.1f} {hy2:.1f}Z" style="fill:{P[col]}"/>')


def axes(P, X0, Y0, X1, Y1, xt, yt, fx, fy, xlab, ylab):
    s = ''
    for v in yt:
        y = fy(v); s += line(X0, y, X1, y, P, 'line', 1) + T(X0 - 6, y + 4, f'{v:g}', P, 11, 'dim', 'end')
    for v in xt:
        x = fx(v); s += line(x, Y1, x, Y1 + 4, P, 'dim', 1) + T(x, Y1 + 17, f'{v:g}', P, 11, 'dim', 'middle')
    s += line(X0, Y1, X1, Y1, P, 'dim', 1.2)
    s += T((X0 + X1) / 2, Y1 + 34, xlab, P, 11.5, 'dim', 'middle')
    s += T(14, (Y0 + Y1) / 2, ylab, P, 11.5, 'dim', 'middle', extra=f'transform="rotate(-90 14 {(Y0 + Y1) / 2:.1f})"')
    return s


# ---------------------------------------------------------------- 1. tree, fork, loop
def fig_tree(P, D):
    W, H = 760, 250; s = ''
    panels = [(20, 'A tree: stock runs it', 'ok'), (270, 'A fork: stock stops, ERROR 133', 'fork'), (520, 'A loop: stock stops, ERROR 131', 'loop')]
    for x0, title, kind in panels:
        s += rect(x0, 10, 220, 230, P, 'soft', 'line', 10)
        s += T(x0 + 110, 32, title, P, 12.5, 'ink', 'middle', 600)
        if kind == 'ok':
            pts = [(x0 + 50, 70), (x0 + 170, 70), (x0 + 110, 135), (x0 + 110, 205)]
            s += arrow(*pts[0], *pts[2], P, 'kw', 2.4) + arrow(*pts[1], *pts[2], P, 'kw', 2.4) + arrow(*pts[2], *pts[3], P, 'kw', 2.4)
            for i, (x, y) in enumerate(pts): s += circle(x, y, 9, P)
            s += T(x0 + 128, 140, '1 out', P, 11, 'dim')
        elif kind == 'fork':
            pts = [(x0 + 110, 62), (x0 + 110, 125), (x0 + 50, 205), (x0 + 170, 205)]
            s += arrow(*pts[0], *pts[1], P, 'kw', 2.4) + arrow(*pts[1], *pts[2], P, 'kw', 2.4) + arrow(*pts[1], *pts[3], P, 'kw', 2.4)
            for (x, y) in pts: s += circle(x, y, 9, P)
            s += circle(x0 + 110, 125, 14, P, 'face', 'd', 2.2) + circle(x0 + 110, 125, 9, P)
            s += T(x0 + 130, 121, '2 outs:', P, 11, 'd') + T(x0 + 130, 135, 'which gets what?', P, 11, 'd')
        else:
            pts = [(x0 + 60, 70), (x0 + 110, 130), (x0 + 160, 70), (x0 + 110, 205)]
            s += arrow(*pts[0], *pts[1], P, 'kw', 2.4) + arrow(*pts[1], *pts[3], P, 'kw', 2.4)
            s += arrow(*pts[1], *pts[2], P, 'd', 2.2, '5 4') + arrow(*pts[2], *pts[0], P, 'd', 2.2, '5 4')
            for (x, y) in pts: s += circle(x, y, 9, P)
            s += T(x0 + 110, 54, 'the water comes back', P, 11, 'd', 'middle')
            s += T(x0 + 150, 112, 'who goes', P, 11, 'd', 'start') + T(x0 + 150, 126, 'first?', P, 11, 'd', 'start')
    return _svg(W, H, s, 'A tree, a fork and a loop')


# ---------------------------------------------------------------- 2. the HEAD rule, drawn
def fig_head(P, D):
    W, H = 760, 330; s = ''
    jx0, jx1, jbot, jtop = 170, 300, 300, 80            # the junction, in elevation
    px1 = 520                                           # where the pipes leave the frame
    d1top = jbot - 90                                   # outlet 1: 3.0 ft at the invert (30 px per ft)
    o2bot = jbot - 105; d2top = o2bot - 45              # outlet 2: 1.5 ft, its invert 3.5 ft up
    yw = o2bot - 22                                     # the shared level y
    s += f'<rect x="{jx0}" y="{yw}" width="{jx1 - jx0}" height="{jbot - yw}" style="fill:{P["a"]};opacity:.22"/>'
    s += path(f'M{jx0} {jtop}V{jbot}H{jx1}V{o2bot}M{jx1} {d2top}V{d1top}M{jx1} {d2top}V{jtop}', P, 'ink', 2.2)
    s += f'<rect x="{jx1}" y="{d1top}" width="{px1 - jx1}" height="{jbot - d1top}" style="fill:{P["kw"]};opacity:.30"/>'
    s += path(f'M{jx1} {d1top}H{px1}M{jx1} {jbot}H{px1}', P, 'ink', 2.2)
    s += f'<rect x="{jx1}" y="{yw}" width="{px1 - jx1}" height="{o2bot - yw}" style="fill:{P["b"]};opacity:.38"/>'
    s += path(f'M{jx1} {d2top}H{px1}M{jx1} {o2bot}H{px1}', P, 'ink', 2.2)
    s += line(jx0 - 40, yw, px1 + 10, yw, P, 'a', 1.6, '6 4')
    s += T(jx0 - 46, yw + 5, 'y', P, 16, 'a', 'end', 700) + T(jx0 - 46, yw + 21, 'the one level', P, 11, 'a', 'end')
    s += arrow(30, jbot - 30, jx0 - 3, jbot - 30, P, 'ink', 2.4) + T(30, jbot - 40, 'Q in', P, 13, 'ink', 'start', 600)
    s += arrow(px1 + 4, (d1top + jbot) / 2, px1 + 34, (d1top + jbot) / 2, P, 'kw', 2.2)
    s += arrow(px1 + 4, (d2top + o2bot) / 2, px1 + 34, (d2top + o2bot) / 2, P, 'b', 2.2)
    s += T(px1 + 42, (d2top + o2bot) / 2 - 4, 'outlet 2, 1.5 ft', P, 12, 'ink', 'start', 600)
    s += T(px1 + 42, (d2top + o2bot) / 2 + 12, 'depth y − offset₂', P, 11.5, 'dim')
    s += T(px1 + 42, (d1top + jbot) / 2 - 4, 'outlet 1, 3.0 ft', P, 12, 'ink', 'start', 600)
    s += T(px1 + 42, (d1top + jbot) / 2 + 12, 'y is above its crown:', P, 11.5, 'dim')
    s += T(px1 + 42, (d1top + jbot) / 2 + 27, 'full, capped at Qfull', P, 11.5, 'dim')
    s += arrow(jx1 + 14, jbot - 3, jx1 + 14, o2bot + 3, P, 'dim', 1.2, None, 5) + arrow(jx1 + 14, o2bot + 3, jx1 + 14, jbot - 3, P, 'dim', 1.2, None, 5)
    s += T(jx1 + 20, jbot - 16, 'offset₂', P, 11, 'dim')
    s += T(380, 28, 'Σ  min( cap_k ,  β_k · S( A( y − offset_k ) ) )  =  Q', P, 15, 'ink', 'middle', 600)
    s += T(380, 47, 'find the one level y at which the outlets together carry exactly what came in', P, 11.5, 'dim', 'middle')
    return _svg(W, H, s, 'The HEAD rule: one level for every outlet')


# ---------------------------------------------------------------- 3. section factor of a circle
def fig_sfactor(P, D):
    W, H = 760, 300; X0, X1, Y0, Y1 = 64, 740, 20, 250
    curve = D['section_factor']
    fx = lambda v: X0 + (X1 - X0) * v; fy = lambda v: Y1 - (Y1 - Y0) * v / 1.15
    s = axes(P, X0, Y0, X1, Y1, [0, .2, .4, .6, .8, 1.0], [0, .25, .5, .75, 1.0], fx, fy, 'depth / diameter', 'flow / full-pipe flow')
    s += line(X0, fy(1), X1, fy(1), P, 'dim', 1.2, '4 4')
    d = 'M' + 'L'.join(f'{fx(y):.1f} {fy(q):.1f}' for y, q in curve)
    s += path(d, P, 'a', 2.6)
    capd = 'M' + 'L'.join(f'{fx(y):.1f} {fy(min(q, 1.0)):.1f}' for y, q in curve)
    s += path(capd, P, 'kw', 2.0, dash='6 4')
    pk = max(curve, key=lambda c: c[1])
    cross = next(y for y, q in curve if q >= 1.0)
    s += circle(fx(pk[0]), fy(pk[1]), 4, P, 'a', 'a') + T(fx(pk[0]) - 8, fy(pk[1]) - 10, f'peak {pk[1]:.3f} at {pk[0]:.2f}', P, 11.5, 'ink', 'end')
    s += circle(fx(cross), fy(1), 4, P, 'kw', 'kw') + T(fx(cross) + 4, fy(1) + 22, f'passes full flow at {cross:.2f}', P, 11.5, 'ink', 'end')
    s += T(fx(0.52), fy(0.30), 'solid: Manning flow in an open circle', P, 11.5, 'a') + T(fx(0.52), fy(0.22), 'dashed: the same, capped at full flow, as HEAD uses it', P, 11.5, 'kw')
    return _svg(W, H, s, 'Section factor of a circular pipe')


# ---------------------------------------------------------------- 4. split shares
def fig_shares(P, D):
    rows = D['split_shares']; W, H = 760, 56 + 44 * len(rows); X0, X1 = 190, 660; s = ''
    fx = lambda v: X0 + (X1 - X0) * v
    s += T(X0, 14, '3.0 ft pipe', P, 11, 'dim') + T(X1 + 8, 14, '1.5 ft pipe', P, 11, 'dim')
    for i, r in enumerate(rows):
        y = 26 + 44 * i; sa = r['share'][0]; qa = r['total'] * sa; qb = r['total'] * r['share'][1]
        col = 'dw' if 'DYNWAVE' in r['name'] else 'kw'
        s += T(X0 - 10, y + 17, r['name'], P, 12, 'ink', 'end', 600 if 'DYNWAVE' in r['name'] else 400)
        s += f'<rect x="{X0}" y="{y}" width="{(X1 - X0) * sa:.1f}" height="24" rx="4" style="fill:{P[col]}"/>'
        s += f'<rect x="{fx(sa) + 2:.1f}" y="{y}" width="{(X1 - X0) * (1 - sa) - 2:.1f}" height="24" rx="4" style="fill:{P[col]};opacity:.35"/>'
        s += T(X0 + 8, y + 17, f'{qa:.2f} cfs  ({100 * sa:.1f}%)', P, 11.5, 'on', 'start', 600)
        s += T(X1 + 8, y + 17, f'{qb:.2f} cfs  ({100 * r["share"][1]:.1f}%)', P, 11.5, 'ink')
    x = fx(rows[0]['share'][0]); s += line(x, 22, x, 26 + 44 * len(rows) - 16, P, 'dw', 1.4, '4 3')
    s += T(X0, H - 8, 'at the moment the total outflow peaks, 20 cfs arriving', P, 11, 'dim')
    return _svg(W, H, s, 'How split.inp shares 20 cfs, by routing and rule')


# ---------------------------------------------------------------- 5. hydrographs at the fork
def fig_hydro(P, D):
    S = D['split_series']; W, H = 760, 300; X0, X1, Y0, Y1 = 64, 740, 16, 250
    k, d = S['KINWAVE, HEAD'], S['DYNWAVE (stock)']; n = len(k['CA']); hrs = n * k['step'] / 3600
    fx = lambda p: X0 + (X1 - X0) * p / (n - 1); fy = lambda v: Y1 - (Y1 - Y0) * v / 22
    s = axes(P, X0, Y0, X1, Y1, [], [0, 5, 10, 15, 20], fx, fy, 'hours', 'flow (cfs)')
    for hv in range(0, int(hrs) + 1):
        x = X0 + (X1 - X0) * hv / hrs; s += line(x, Y1, x, Y1 + 4, P, 'dim') + T(x, Y1 + 17, str(hv), P, 11, 'dim', 'middle')
    for key, col in (('C1', 'dim'), ('CA', 'a'), ('CB', 'b')):
        for run, dash, w in ((d, '7 5', 1.8), (k, None, 2.4)):
            ser = run[key]; s += path('M' + 'L'.join(f'{fx(p):.1f} {fy(v):.1f}' for p, v in enumerate(ser)), P, col, w, dash=dash)
    s += T(fx(n * 0.36), fy(20.8), 'inflow pipe C1', P, 11.5, 'dim')
    s += T(fx(n * 0.36), fy(15.6), '3.0 ft outlet CA', P, 11.5, 'a')
    s += T(fx(n * 0.36), fy(6.6), '1.5 ft outlet CB', P, 11.5, 'b')
    s += line(X1 - 220, Y0 + 10, X1 - 196, Y0 + 10, P, 'ink', 2.4) + T(X1 - 190, Y0 + 14, 'swmm5-kw, KINWAVE + HEAD', P, 11.5, 'ink')
    s += line(X1 - 220, Y0 + 28, X1 - 196, Y0 + 28, P, 'ink', 1.8, '7 5') + T(X1 - 190, Y0 + 32, 'stock EPA, DYNWAVE', P, 11.5, 'ink')
    return _svg(W, H, s, 'Flows at the fork in split.inp')


# ---------------------------------------------------------------- 6. the loop step
def fig_loopstep(P, D):
    W, H = 760, 270; s = ''
    boxes = [(20, 'Snapshot', 'the step’s starting state:', 'nodes, conduits, flows'),
             (200, 'Guess', 'each loop-closing link’s', 'outflow = last step’s'),
             (380, 'Sweep', 'stock KW or steady flow,', 'upstream to downstream'),
             (560, 'Compare', 'routed outflow against', 'the guess')]
    for x, t, a, b in boxes:
        s += rect(x, 60, 160, 84, P, 'soft', 'line', 10)
        s += T(x + 80, 86, t, P, 14, 'ink', 'middle', 700) + T(x + 80, 108, a, P, 11, 'dim', 'middle') + T(x + 80, 124, b, P, 11, 'dim', 'middle')
    for x in (180, 360, 540): s += arrow(x, 102, x + 18, 102, P, 'ink', 2)
    # loop back
    s += path('M640 144V196H280V150', P, 'd', 2, dash='6 4') + f'<path d="M280 146L274 158L286 158Z" style="fill:{P["d"]}"/>'
    s += T(460, 214, 'not settled: restore the snapshot, guess = routed (blend 0.5 from sweep 20), sweep again', P, 11.5, 'd', 'middle')
    s += arrow(720, 102, 748, 102, P, 'kw', 2.2)
    s += T(740, 36, 'settled, or 60 sweeps: book the leftover', P, 11.5, 'kw', 'end') + T(740, 51, '(routed − guess) to the node, finish the step', P, 11.5, 'kw', 'end')
    st = D['nets']['loopactive']['stats']
    s += T(380, 250, f'loopactive.inp: {int(st[4])} steps, mean {st[5]:.2f} sweeps, {int(st[7])} steps reached the cap, largest leftover {st[8]:.4f} cfs', P, 11.5, 'ink', 'middle')
    return _svg(W, H, s, 'One routing step on a network with a loop')


# ---------------------------------------------------------------- 7. the pipe that ran backwards
def fig_backwards(P, D):
    L = D['loop_series']; W, H = 760, 300; X0, X1, Y0, Y1 = 64, 740, 16, 250
    n = len(L['kw']); hrs = n * L['step'] / 3600
    lo, hi = -4, 1.5
    fx = lambda p: X0 + (X1 - X0) * p / (n - 1); fy = lambda v: Y1 - (Y1 - Y0) * (v - lo) / (hi - lo)
    s = axes(P, X0, Y0, X1, Y1, [], [-4, -3, -2, -1, 0, 1], fx, fy, 'hours', 'flow in R1 (cfs), + is J3 → J1')
    for hv in range(0, int(hrs) + 1):
        x = X0 + (X1 - X0) * hv / hrs; s += line(x, Y1, x, Y1 + 4, P, 'dim') + T(x, Y1 + 17, str(hv), P, 11, 'dim', 'middle')
    s += line(X0, fy(0), X1, fy(0), P, 'dim', 1.4)
    s += path('M' + 'L'.join(f'{fx(p):.1f} {fy(v):.1f}' for p, v in enumerate(L['dw'])), P, 'dw', 2.2, dash='7 5')
    s += path('M' + 'L'.join(f'{fx(p):.1f} {fy(v):.1f}' for p, v in enumerate(L['kw'])), P, 'kw', 2.6)
    mn = min(L['dw']); mx = max(L['kw'])
    s += T(fx(n * 0.5), fy(mn) + 18, f'DYNWAVE: R1 runs backwards, J1 → J3, down to {mn:.2f} cfs', P, 11.5, 'dw', 'middle')
    s += T(fx(n * 0.5), fy(mx) - 8, f'swmm5-kw: forwards, J3 → J1, up to {mx:.2f} cfs', P, 11.5, 'kw', 'middle')
    return _svg(W, H, s, 'Flow in the relief pipe R1 of loopactive.inp')


# ---------------------------------------------------------------- 8. stock KW continuity through capacity
def fig_chain(P, D):
    C = D['chain_sweep']; W, H = 760, 300; X0, X1, Y0, Y1 = 64, 740, 16, 250
    lo, hi = -11, 1; q0, q1 = C[0]['q'], C[-1]['q']
    fx = lambda q: X0 + (X1 - X0) * (q - q0) / (q1 - q0); fy = lambda v: Y0 + (Y1 - Y0) * (hi - v) / (hi - lo)
    s = axes(P, X0, Y0, X1, Y1, [20, 25, 30, 35, 40, 45], [-10, -8, -6, -4, -2, 0], fx, fy, 'held inflow (cfs), three 3 ft pipes in series', 'routing continuity error (%)')
    s += line(fx(33.35), Y0, fx(33.35), Y1, P, 'a', 1.4, '5 4') + T(fx(33.35) - 6, Y0 + 12, 'full-pipe capacity 33.35 cfs', P, 11.5, 'a', 'end')
    s += path('M' + 'L'.join(f'{fx(c["q"]):.1f} {fy(c["musl"]):.1f}' for c in C), P, 'epa', 2.4)
    for c in C: s += circle(fx(c['q']), fy(c['musl']), 2.6, P, 'epa', 'epa', 0)
    w = min(C, key=lambda c: c['musl'])
    s += T(fx(w['q']) + 8, fy(w['musl']) + 4, f'{w["musl"]:.2f}% at {w["q"]:g} cfs', P, 11.5, 'ink')
    for q in (30, 34, 40):
        c = next(c for c in C if abs(c['q'] - q) < 1e-6); s += circle(fx(q), fy(c['musl']), 5.5, P, 'face', 'ink', 1.4)
    s += T(fx(21), fy(-6.5), 'open rings: the three inflows', P, 11.5, 'dim') + T(fx(21), fy(-7.4), 'measured in September', P, 11.5, 'dim')
    return _svg(W, H, s, 'Stock 5.2.4 kinematic wave continuity through pipe capacity')


# ---------------------------------------------------------------- 9. every link peak, KW against DW
def fig_peaks(P, D):
    pk = D['peaks']; W, H = 760, 340; X0, X1, Y0, Y1 = 70, 470, 16, 300; top = 40
    fx = lambda v: X0 + (X1 - X0) * v / top; fy = lambda v: Y1 - (Y1 - Y0) * v / top
    s = axes(P, X0, Y0, X1, Y1, [0, 10, 20, 30, 40], [0, 10, 20, 30, 40], fx, fy, 'peak flow, DYNWAVE (cfs)', 'peak flow, swmm5-kw (cfs)')
    s += line(fx(0), fy(0), fx(top), fy(top), P, 'dim', 1.2, '4 4')
    cols = dict(split='a', diamond='c', braid='b', loopactive='e', loop='d')
    def mark(m, x, y):
        c = P[cols[m]]; st = f'style="fill:none;stroke:{c};stroke-width:1.8"'
        if m == 'split': return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" {st}/>'
        if m == 'diamond': return f'<path d="M{x:.1f} {y - 7:.1f}L{x + 7:.1f} {y:.1f}L{x:.1f} {y + 7:.1f}L{x - 7:.1f} {y:.1f}Z" {st}/>'
        if m == 'braid': return f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" {st}/>'
        if m == 'loopactive': return f'<path d="M{x:.1f} {y - 6:.1f}L{x + 6:.1f} {y + 5:.1f}L{x - 6:.1f} {y + 5:.1f}Z" {st}/>'
        return f'<path d="M{x - 5:.1f} {y - 5:.1f}L{x + 5:.1f} {y + 5:.1f}M{x + 5:.1f} {y - 5:.1f}L{x - 5:.1f} {y + 5:.1f}" {st}/>'
    for p in pk:
        s += mark(p['model'], fx(max(0, p['dw'])), fy(max(0, p['kw'])))
    y = 40
    for m in cols:
        s += mark(m, 500, y - 4) + T(514, y, m + '.inp', P, 12, 'ink'); y += 22
    s += T(500, y + 14, 'Tree-like splits sit on the line.', P, 11.5, 'dim')
    s += T(500, y + 30, 'The loops do not: dynamic wave', P, 11.5, 'dim')
    s += T(500, y + 46, 'surcharges and reverses pipes that', P, 11.5, 'dim')
    s += T(500, y + 62, 'kinematic wave can only fill.', P, 11.5, 'dim')
    return _svg(W, H, s, 'Peak flow in every link of the five test networks')


# ---------------------------------------------------------------- 10. the corpus
def fig_corpus(P, D):
    C = D.get('corpus_fig')
    W, H = 760, 70 + 58 * (len(C) if C else 1); s = ''
    if not C: return _svg(W, H, T(20, 40, 'corpus results pending', P, 13, 'dim'), 'Corpus')
    X0, X1 = 200, 740; mx = max(r['n'] for r in C)
    for i, r in enumerate(C):
        y = 16 + 58 * i; w = (X1 - X0) * r['n'] / mx
        s += T(X0 - 10, y + 17, r['label'], P, 12, 'ink', 'end', 600) + T(X0 - 10, y + 32, f"{r['n']:,} models", P, 11, 'dim', 'end')
        x = X0
        for k, col in (('same', 'kw'), ('ran', 'a'), ('inc', 'dim'), ('diff', 'd')):
            v = r.get(k, 0)
            if v <= 0: continue
            ww = max(3, w * v / r['n']); s += f'<rect x="{x:.1f}" y="{y}" width="{ww:.1f}" height="24" style="fill:{P[col]}"/>'; x += ww
        s += T(X0, y + 40, r['text'], P, 11.5, 'ink')
    y = 16 + 58 * len(C) + 8
    s += f'<rect x="{X0}" y="{y}" width="12" height="12" style="fill:{P["kw"]}"/>' + T(X0 + 18, y + 10, 'byte-identical to stock', P, 11.5, 'dim')
    s += f'<rect x="{X0 + 180}" y="{y}" width="12" height="12" style="fill:{P["a"]}"/>' + T(X0 + 198, y + 10, 'refused by stock, run by swmm5-kw', P, 11.5, 'dim')
    s += f'<rect x="{X0 + 420}" y="{y}" width="12" height="12" style="fill:{P["dim"]}"/>' + T(X0 + 438, y + 10, 'stock crashes or never ends', P, 11.5, 'dim')
    return _svg(W, H, s, 'The corpus gate')


# ---------------------------------------------------------------- 11. flat channels
def fig_flat(P, D):
    F = D['flat_channel']; W, H = 760, 300; X0, X1, Y0, Y1 = 70, 600, 20, 250
    drops = sorted(set(c['drop_ft'] for c in F)); qs = sorted(set(c['q_cfs'] for c in F))
    v = {(c['drop_ft'], c['q_cfs']): c['musl'] for c in F}
    lo = -12; fy = lambda y: Y0 + (Y1 - Y0) * (0 - y) / (0 - lo)
    s = ''
    for g in (0, -2, -4, -6, -8, -10, -12):
        s += line(X0, fy(g), X1, fy(g), P, 'line', 1) + T(X0 - 6, fy(g) + 4, f'{g}', P, 11, 'dim', 'end')
    s += T(14, (Y0 + Y1) / 2, 'routing continuity error (%)', P, 11.5, 'dim', 'middle', extra=f'transform="rotate(-90 14 {(Y0 + Y1) / 2:.1f})"')
    gw = (X1 - X0) / len(drops); bw = gw / (len(qs) + 1.5); cols = ['d', 'b', 'a']
    for i, d in enumerate(drops):
        for j, q in enumerate(qs):
            x = X0 + i * gw + bw * (0.75 + j); y = v[(d, q)]
            s += f'<rect x="{x:.1f}" y="{fy(0):.1f}" width="{bw - 4:.1f}" height="{fy(y) - fy(0):.1f}" style="fill:{P[cols[j]]}"/>'
            s += T(x + (bw - 4) / 2, fy(y) + 14, f'{y:.1f}', P, 10.5, 'ink', 'middle')
        s += T(X0 + i * gw + gw / 2, Y1 + 18, ('no fall (WARNING 04)' if d == 0 else f'{d:g} ft fall'), P, 11.5, 'ink', 'middle', 600)
    s += line(X0, fy(0), X1, fy(0), P, 'dim', 1.2)
    for j, q in enumerate(qs):
        s += f'<rect x="{X1 + 24}" y="{40 + 22 * j}" width="12" height="12" style="fill:{P[cols[j]]}"/>' + T(X1 + 42, 50 + 22 * j, f'{q:g} cfs inflow', P, 11.5, 'ink')
    s += T(X1 + 24, 130, 'one 1,000 ft trapezoidal', P, 11, 'dim') + T(X1 + 24, 145, 'channel, one day,', P, 11, 'dim') + T(X1 + 24, 160, 'stock 5.2.4 KINWAVE', P, 11, 'dim')
    return _svg(W, H, s, 'Stock kinematic wave continuity in a flat channel')


FIGS = dict(tree=fig_tree, head=fig_head, sfactor=fig_sfactor, shares=fig_shares, hydro=fig_hydro,
            loopstep=fig_loopstep, backwards=fig_backwards, chain=fig_chain, peaks=fig_peaks, corpus=fig_corpus, flat=fig_flat)
