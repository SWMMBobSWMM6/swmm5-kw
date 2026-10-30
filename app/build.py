#!/usr/bin/env python3
"""Build dist/swmm5-kw.html (one self-contained file) and the essay sources for the .docx.

  python3 app/build.py

Reads wasm/, models/, results/ (gates.json, summary.json, figdata.json) and app/doc/.
Then `node app/doc/build_docx.js` writes dist/swmm5-kw-doc.docx from app/doc/out/.
"""
import base64, datetime, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'doc'))
import essay, figures

MODEL_INFO = {
    'split.inp': ('fork', 'One 3 ft pipe carrying 20 cfs into a junction with a 3.0 ft and a 1.5 ft outlet. Stock KINWAVE: ERROR 133.'),
    'diamond.inp': ('fork and merge', 'Splits into two equal paths of two pipes each, which meet again. Stock KINWAVE: ERROR 133.'),
    'braid.inp': ('two forks', 'Two splits and two merges in series. Stock KINWAVE: ERROR 133.'),
    'loopactive.inp': ('relief loop', 'A 1.5 ft relief pipe from the bottom junction back to the top, 3.5 ft above the invert. Stock: ERROR 131.'),
    'loop.inp': ('loop past capacity', 'The relief loop driven past capacity with a 2 ft outlet; it floods. Stock: ERROR 131.'),
    'chain30.inp': ('tree, 30 cfs', 'Three 3 ft pipes in series at 30 cfs, below the 33.35 cfs capacity. Nothing to split: same bytes as stock.'),
    'chain34.inp': ('tree, 34 cfs', 'The same chain just above capacity, where stock kinematic wave loses 1.6% of its water.'),
    'chain40.inp': ('tree, 40 cfs', 'The same chain well above capacity.'),
    'storage.inp': ('storage outlets', 'A storage unit with two outlets: storage keeps its stock rules, so nothing changes.'),
    'split_dynwave.inp': ('fork, DYNWAVE', 'split.inp under dynamic wave: the extension never touches it.'),
    'diamond_dynwave.inp': ('fork and merge, DYNWAVE', 'diamond.inp under dynamic wave.'),
    'braid_dynwave.inp': ('two forks, DYNWAVE', 'braid.inp under dynamic wave.'),
    'loopactive_dynwave.inp': ('relief loop, DYNWAVE', 'loopactive.inp under dynamic wave: the relief pipe runs backwards.'),
}
ORDER = ['split.inp', 'diamond.inp', 'braid.inp', 'loopactive.inp', 'loop.inp', 'chain30.inp', 'chain34.inp', 'chain40.inp', 'storage.inp',
         'split_dynwave.inp', 'diamond_dynwave.inp', 'braid_dynwave.inp', 'loopactive_dynwave.inp']


def main():
    D, S = essay.load_data()
    G = json.load(open(os.path.join(R, 'results', 'gates.json')))
    B = essay.blocks(D, S)
    essay_html = essay.to_html(B, {k: (lambda P, f=f: f(P, D)) for k, f in figures.FIGS.items()}, figures.APP)
    # docx sources: blocks as JSON, figures as light-theme SVG
    out = os.path.join(HERE, 'doc', 'out'); os.makedirs(out, exist_ok=True)
    json.dump(essay.to_json(B), open(os.path.join(out, 'essay.json'), 'w'), indent=1)
    for k, f in figures.FIGS.items(): open(os.path.join(out, f'fig_{k}.svg'), 'w').write(f(figures.DOCX, D))

    models = [dict(name=n, label=MODEL_INFO[n][0], desc=MODEL_INFO[n][1], text=open(os.path.join(R, 'models', n)).read()) for n in ORDER]
    corpus = None
    if S.get('passes'):
        rows = [[p['label'], f"{p['models']:,}", f"{p['identical']:,}", str(p['census_ran']), str(p['crash_same']), str(p['different']), str(p['inconclusive'])] for p in S['passes']]
        T = S['total']
        rows.append(['All', f"{T['models']:,}", f"{T['identical']:,}", str(T['census_ran']), str(T['crash_same']), str(T['different']), str(T['inconclusive'])])
        cen = ', '.join(c['inp'] for c in S['census'])
        corpus = dict(summary=f"{S['models']:,} models from SWMMBobSWMM6/1729-SWMM5-Models-2030 (commit 9ee63bd), the set swmm5-rust was gated on, through stock 5.2.4 and swmm5-kw: {T['runs']:,} engine runs. KINWAVE and STEADY models ran with the extension off and with each split rule; the rest with HEAD and loops on.",
                      rows=rows, note=f"Refused by stock and run by swmm5-kw: {cen or 'none'}. Stock crashes: OpenSWMM 2026 code-review decks on which EPA 5.2.4 itself dies with a signal; swmm5-kw dies at the same point with the same partial output. Inconclusive: " + '; '.join(f"{i['inp']} ({i['why']})" for i in S['inconclusive']) + '.')
    if corpus and S.get('whatif'):
        Wf = S['whatif']
        corpus['whatif'] = (f"What-if: the {Wf['models']:,} DYNWAVE models switched to KINWAVE. Stock refused {Wf['census']:,} with ERROR 133 or 131; swmm5-kw ran {Wf['census_ran']:,} of them to the end "
                            f"and stopped on another kinematic-wave check in {Wf['census_error']:,}. Where stock could run the switched model, swmm5-kw was identical in {Wf['identical']:,} of {Wf['stock_ran']:,} and different in {Wf['different']}.")
    sha = {e[0]: e for e in G['engines']}
    engines = [[f, f"{os.path.getsize(os.path.join(R, 'wasm', f)):,}", sha[f][2] if f in sha else ''] for f in ('swmm524kw.wasm', 'swmm524.wasm')]
    results = dict(gates=[[g[0], g[1]] for g in G['gates']], corpus=corpus, engines=engines)

    t = open(os.path.join(HERE, 'app_template.html')).read()
    rep = {
        '@@BUILD@@': f"{datetime.date.today().isoformat()} wasm {sha.get('swmm524kw.wasm', ['', '', ''])[2][:12]}",
        '@@WASM_KW@@': base64.b64encode(open(os.path.join(R, 'wasm', 'swmm524kw.wasm'), 'rb').read()).decode(),
        '@@WASM_STOCK@@': base64.b64encode(open(os.path.join(R, 'wasm', 'swmm524.wasm'), 'rb').read()).decode(),
        '@@MODELS@@': json.dumps(models).replace('</', '<\\/'),
        '@@RESULTS@@': json.dumps(results).replace('</', '<\\/'),
        '@@SHIM@@': open(os.path.join(R, 'wasm', 'wasi-shim.iife.js')).read(),
        '@@KWENGINE@@': open(os.path.join(R, 'wasm', 'kwengine.js')).read(),
        '@@APP@@': open(os.path.join(HERE, 'app.js')).read(),
        '@@ESSAY@@': essay_html,
    }
    for k, v in rep.items():
        assert t.count(k) == 1, k
        t = t.replace(k, v)
    os.makedirs(os.path.join(R, 'dist'), exist_ok=True)
    open(os.path.join(R, 'dist', 'swmm5-kw.html'), 'w').write(t)
    # the claude.ai artifact wraps the page in its own document skeleton: body content only
    a = t[t.index('<title>'):t.index('</head>')] + t[t.index('<body>') + len('<body>'):t.index('</body>')]
    a = a.replace('<meta charset="utf-8">\n', '').replace('<meta name="viewport" content="width=device-width, initial-scale=1">\n', '')
    os.makedirs(os.path.join(HERE, 'doc', 'out'), exist_ok=True)
    open(os.path.join(HERE, 'doc', 'out', 'swmm5-kw-artifact.html'), 'w').write(a)
    print('dist/swmm5-kw.html', f'{len(t):,} bytes;', len([b for b in B if b[0] == 'fig']), 'figures; artifact variant', f'{len(a):,} bytes')


if __name__ == '__main__':
    main()
