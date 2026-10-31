/* swmm5-kw app: stock EPA SWMM 5.2.4 and swmm5-kw (wasm32-wasi reactors) side by side.
   Engines run on the main thread in ~28 ms slices (wasm/kwengine.js), so the page stays live. */
'use strict';
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const MODELS = JSON.parse($('#models-json').textContent);
const RESULTS = JSON.parse($('#results-json').textContent);
const MOD = { kw: null, stock: null };
const RULES = { 0: 'off', 1: 'HEAD', 2: 'CAPACITY', 3: 'AREA' };
const UNITS = ['CFS', 'GPM', 'MGD', 'CMS', 'LPS', 'MLD'];
let CUR = null, RUN = null, STOP = false, BUSY = false, RPTSEL = 'kw', RUNSEQ = 0;

function toast(msg) { const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 2600); }
function fmt(x, d = 3) { if (x == null || !isFinite(x)) return '–'; const a = Math.abs(x); if (a !== 0 && (a < 1e-3 || a >= 1e6)) return x.toExponential(2); return x.toFixed(d); }
function b64bytes(id) { const s = $(id).textContent.trim(), bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
async function sha256(u8) { try { const h = await crypto.subtle.digest('SHA-256', u8); return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, '0')).join(''); } catch (e) { return null; } }

/* ---------------------------------------------------------------- theme and tabs */
let THEME_PREF = 'dark';
const prefersDark = () => { try { return matchMedia('(prefers-color-scheme: dark)').matches; } catch (e) { return true; } };
function applyTheme(pref) {
  THEME_PREF = (pref === 'light' || pref === 'auto') ? pref : 'dark';
  const t = THEME_PREF === 'auto' ? (prefersDark() ? 'dark' : 'light') : THEME_PREF;
  document.documentElement.setAttribute('data-theme', t);
  $$('#theme-toggle button').forEach(b => b.classList.toggle('on', b.dataset.t === THEME_PREF));
  try { localStorage.setItem('swmm5kw_theme', THEME_PREF); } catch (e) {}
  if (RUN) drawChart();
}
$$('#theme-toggle button').forEach(b => b.addEventListener('click', () => applyTheme(b.dataset.t)));
try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (THEME_PREF === 'auto') applyTheme('auto'); }); } catch (e) {}
function showView(v) {
  $$('.view').forEach(s => { s.hidden = s.id !== 'view-' + v; });
  $$('#tablist button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.view === v)));
  try { history.replaceState(null, '', '#' + v); } catch (e) {}
}
$$('#tablist button').forEach(b => b.addEventListener('click', () => showView(b.dataset.view)));

/* ---------------------------------------------------------------- saving files */
let DL = null;
(async () => { try { if (window.claude && claude.use) DL = await claude.use('downloads'); } catch (e) { DL = null; } })();
async function save(filename, data, type) {
  if (DL) {
    try { await DL.save({ filename, data }); toast('Saved ' + filename); } catch (e) { if (e && e.code !== 'declined') toast('Could not save: ' + (e.message || e.code)); }
    return;
  }
  try {
    const blob = data instanceof Blob ? data : new Blob([data], { type: type || 'application/octet-stream' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  } catch (e) { toast('This page cannot save files here.'); }
}

/* ---------------------------------------------------------------- .inp helpers */
function routingOf(inp) {
  let sec = '';
  for (const raw of inp.split(/\r?\n/)) {
    const s = raw.split(';')[0].trim(); if (!s) continue;
    if (s[0] === '[') { sec = s.toUpperCase(); continue; }
    if (sec === '[OPTIONS]') { const p = s.split(/\s+/); if (p.length > 1 && p[0].toUpperCase() === 'FLOW_ROUTING') return p[1].toUpperCase(); }
  }
  return 'KINWAVE';
}
function setRouting(inp, method) {
  const lines = inp.split(/\r?\n/); let sec = '', optAt = -1;
  for (let i = 0; i < lines.length; i++) {
    const s = lines[i].split(';')[0].trim(); if (!s) continue;
    if (s[0] === '[') { sec = s.toUpperCase(); if (sec === '[OPTIONS]') optAt = i; continue; }
    if (sec === '[OPTIONS]' && /^FLOW_ROUTING\b/i.test(s)) { lines[i] = 'FLOW_ROUTING         ' + method; return lines.join('\n'); }
  }
  if (optAt >= 0) { lines.splice(optAt + 1, 0, 'FLOW_ROUTING         ' + method); return lines.join('\n'); }
  return '[OPTIONS]\nFLOW_ROUTING         ' + method + '\n\n' + inp;
}
function durationDays(inp) {
  const o = {}; let sec = '';
  for (const raw of inp.split(/\r?\n/)) {
    const s = raw.split(';')[0].trim(); if (!s) continue;
    if (s[0] === '[') { sec = s.toUpperCase(); continue; }
    if (sec === '[OPTIONS]') { const p = s.split(/\s+/); if (p.length > 1) o[p[0].toUpperCase()] = p[1]; }
  }
  const d = (ds, ts) => { const m = /^(\d+)\/(\d+)\/(\d+)$/.exec(ds || ''); if (!m) return null; const t = (ts || '0:0:0').split(':').map(Number); return Date.UTC(+m[3], +m[1] - 1, +m[2], t[0] || 0, t[1] || 0, t[2] || 0); };
  const a = d(o.START_DATE, o.START_TIME), b = d(o.END_DATE || o.START_DATE, o.END_TIME);
  return (a != null && b != null && b > a) ? (b - a) / 864e5 : 0;
}
function reportPeriods(inp) {   // reporting periods a complete run writes: (END - REPORT_START) / REPORT_STEP
  const o = {}; let sec = '';
  for (const raw of inp.split(/\r?\n/)) {
    const s = raw.split(';')[0].trim(); if (!s) continue;
    if (s[0] === '[') { sec = s.toUpperCase(); continue; }
    if (sec === '[OPTIONS]') { const p = s.split(/\s+/); if (p.length > 1) o[p[0].toUpperCase()] = p[1]; }
  }
  const d = (ds, ts) => { const m = /^(\d+)\/(\d+)\/(\d+)$/.exec(ds || ''); if (!m) return null; const t = (ts || '0:0:0').split(':').map(Number); return Date.UTC(+m[3], +m[1] - 1, +m[2], t[0] || 0, t[1] || 0, t[2] || 0); };
  const st = (ts, def) => { if (!ts) return def; const t = ts.split(':').map(Number); return (t[0] || 0) * 3600 + (t[1] || 0) * 60 + (t[2] || 0); };
  const a = d(o.REPORT_START_DATE || o.START_DATE, o.REPORT_START_TIME || o.START_TIME), b = d(o.END_DATE || o.START_DATE, o.END_TIME), step = st(o.REPORT_STEP, 900);
  return (a != null && b != null && b > a && step > 0) ? Math.floor((b - a) / 1000 / step + 1e-9) : null;
}
function topology(inp) {   // link -> [from, to, kind], from the five link sections
  const T = {}; let sec = '';
  const kinds = { '[CONDUITS]': 'conduit', '[PUMPS]': 'pump', '[ORIFICES]': 'orifice', '[WEIRS]': 'weir', '[OUTLETS]': 'outlet' };
  for (const raw of inp.split(/\r?\n/)) {
    const s = raw.split(';')[0].trim(); if (!s) continue;
    if (s[0] === '[') { sec = s.toUpperCase(); continue; }
    if (kinds[sec]) { const p = s.split(/\s+/); if (p.length >= 3) T[p[0].toUpperCase()] = [p[1], p[2], kinds[sec]]; }
  }
  return T;
}

/* ---------------------------------------------------------------- .out and .rpt readers */
function readOut(u8) {
  if (!u8 || u8.length < 64) return null;
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength), n = u8.length, I = o => dv.getInt32(o, true);
  if (I(0) !== 516114522 || I(n - 4) !== 516114522) return null;
  const nSub = I(12), nNode = I(16), nLink = I(20), nPoll = I(24), flowUnits = I(8);
  const idPos = I(n - 24), propPos = I(n - 20), outPos = I(n - 16), nP = I(n - 12);
  const dec = new TextDecoder('latin1'); let o = idPos;
  const rd = () => { const L = I(o); o += 4; const s = dec.decode(u8.subarray(o, o + L)); o += L; return s; };
  const subs = [], nodes = [], links = [];
  for (let i = 0; i < nSub; i++) subs.push(rd());
  for (let i = 0; i < nNode; i++) nodes.push(rd());
  for (let i = 0; i < nLink; i++) links.push(rd());
  o = propPos;
  const ns = I(o); o += 4 + 4 * ns + 4 * ns * nSub;
  const nn = I(o); o += 4 + 4 * nn + 4 * nn * nNode;
  const nl = I(o); o += 4 + 4 * nl + 4 * nl * nLink;
  const nSV = I(o); o += 4 + 4 * nSV; const nNV = I(o); o += 4 + 4 * nNV; const nLV = I(o); o += 4 + 4 * nLV; const nYV = I(o); o += 4 + 4 * nYV;
  const start = dv.getFloat64(o, true); o += 8; const step = I(o);
  const rec = 8 + 4 * (nSub * nSV + nNode * nNV + nLink * nLV + nYV);
  const linkIx = new Map(links.map((id, i) => [id.toUpperCase(), i]));
  // the time of every reporting period, in hours from the report start, read from the records themselves:
  // the first record is one report step after the start, not at it (v1.0 plotted sample p at p steps)
  const hours = new Float64Array(nP);
  for (let p = 0; p < nP; p++) hours[p] = (dv.getFloat64(outPos + p * rec, true) - start) * 24;
  return { dv, nSub, nNode, nLink, nPoll, flowUnits, subs, nodes, links, linkIx, nP, outPos, rec, nSV, nNV, nLV, nYV, start, step, hours };
}
function linkSeries(O, li, v = 0) {
  const a = new Float32Array(O.nP), base = 8 + 4 * (O.nSub * O.nSV + O.nNode * O.nNV + li * O.nLV + v);
  for (let p = 0; p < O.nP; p++) a[p] = O.dv.getFloat32(O.outPos + p * O.rec + base, true);
  return a;
}
function readRpt(t) {
  const errs = [...t.matchAll(/ERROR (\d+):?\s*([^\n]*)/g)].map(m => ({ code: +m[1], text: m[2].trim() }));
  const cont = label => { const i = t.indexOf(label); if (i < 0) return null; const m = /Continuity Error \(%\) \.+\s+(\S+)/.exec(t.slice(i)); return m ? m[1] : null; };
  const out = { errs, routing: cont('Flow Routing Continuity'), runoff: cont('Runoff Quantity Continuity'), kw: null, loopLine: null };
  const k = t.indexOf('KW/SF extension (modified engine');
  if (k >= 0) {
    const lines = t.slice(k).split('\n'); let mode = '', rule = '';
    const kw = { split: [], loops: [] };
    for (const L of lines.slice(2, 400)) {
      let m;
      if ((m = /Multi-outlet junctions \.+ (\d+)\s+\(allocation (\w+)\)/.exec(L))) { mode = 'split'; rule = m[2]; continue; }
      if (/Loop-closing links \.+ (\d+)/.test(L)) { mode = 'loops'; continue; }
      if (/^\s*$/.test(L) || /\*{5}/.test(L)) break;
      if (mode) kw[mode].push(...L.trim().split(/\s+/));
    }
    kw.rule = rule; out.kw = kw;
  }
  const li = /Loop iteration: ([^\n]*)/.exec(t); if (li) out.loopLine = li[1].trim();
  return out;
}

/* ---------------------------------------------------------------- run identity
   Every result on the page belongs to the run that made it. RUN.meta is fixed when the run starts;
   when the inputs on the left no longer match it, the results are marked stale and the export keeps
   the run's own name. (v1.0 named the CSV after whatever model was selected at export time.) */
function inputs() {
  return { name: CUR ? CUR.name : '', text: CUR ? CUR.text : '', routingSel: $('#routingSel').value, split: +$('#splitSel').value, loop: $('#loopOn').checked ? 1 : 0, dw: $('#dwOn').checked ? 1 : 0 };
}
const sameInputs = (a, b) => a && b && a.name === b.name && a.text === b.text && a.routingSel === b.routingSel && a.split === b.split && a.loop === b.loop && a.dw === b.dw;
function runLabel(m) { return `${m.name}, ${m.routing}, split ${RULES[m.split]}, loops ${m.loop ? 'iterated' : 'off'}`; }
function markStale() {
  const n = $('#staleNote'); if (!n) return;
  const stale = !!(RUN && !sameInputs(RUN.meta.inputs, inputs()));
  n.classList.toggle('hidden', !stale); $('#results').classList.toggle('stale', stale);
  if (stale) n.innerHTML = `<b>These results are from run ${RUN.meta.id}: ${esc(runLabel(RUN.meta))}.</b> The inputs have changed since${CUR && CUR.name !== RUN.meta.name ? ` (now ${esc(CUR.name)})` : ''}; run again to see results for them. Export CSV still saves run ${RUN.meta.id}, under its own name.`;
}
['#routingSel', '#splitSel', '#loopOn', '#dwOn'].forEach(id => $(id).addEventListener('change', markStale));

/* ---------------------------------------------------------------- model picker */
function setModel(name, text, desc) {
  CUR = { name, text };
  $('#modelDesc').textContent = desc || (name + ' · ' + routingOf(text) + ' · ' + text.length.toLocaleString() + ' characters');
  markStale();
}
function fillModels() {
  const sel = $('#modelSel');
  sel.innerHTML = MODELS.map((m, i) => `<option value="${i}">${esc(m.name)}${m.label ? ' — ' + esc(m.label) : ''}</option>`).join('');
  sel.addEventListener('change', () => { const m = MODELS[+sel.value]; setModel(m.name, m.text, m.desc); });
  const first = MODELS.findIndex(m => m.name === 'split.inp');
  sel.value = String(first >= 0 ? first : 0); const m = MODELS[+sel.value]; setModel(m.name, m.text, m.desc);
}
function loadFile(f) {
  const r = new FileReader();
  r.onload = () => {
    const txt = new TextDecoder('latin1').decode(new Uint8Array(r.result));
    if (!/\[(JUNCTIONS|OUTFALLS|OPTIONS|SUBCATCHMENTS|CONDUITS)\]/i.test(txt)) { toast('That file has no SWMM sections.'); return; }
    setModel(f.name, txt, null);
    let opt = $('#modelSel').querySelector('option[data-user]');
    if (!opt) { opt = document.createElement('option'); opt.dataset.user = '1'; $('#modelSel').prepend(opt); }
    opt.value = 'user'; opt.textContent = f.name + ' (yours)'; $('#modelSel').value = 'user';
    toast('Loaded ' + f.name);
  };
  r.readAsArrayBuffer(f);
}
$('#fileIn').addEventListener('change', e => { if (e.target.files[0]) loadFile(e.target.files[0]); });
const drop = $('#drop');
['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => { const f = e.dataTransfer.files[0]; if (f) loadFile(f); });

/* ---------------------------------------------------------------- engine cards */
const ENG = {
  stock: { name: 'Stock EPA 5.2.4', color: 'var(--epa)', what: '' },
  kw: { name: 'swmm5-kw', color: 'var(--kw)', what: '' },
  dw: { name: 'Reference', color: 'var(--dw)', what: 'stock EPA 5.2.4 with FLOW_ROUTING DYNWAVE' },
};
function engCards(st) {
  $('#engCards').innerHTML = ['stock', 'kw', 'dw'].map(k => {
    const e = ENG[k], s = st[k] || {};
    const dl = s.rows ? s.rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join('') : '';
    return `<div class="eng" id="eng-${k}"><div class="name"><span class="dot" style="background:${e.color}"></span>${e.name}</div>
      <div class="what">${esc(s.what || e.what)}</div>${s.tag || ''}
      <div class="prog"><span style="background:${e.color};width:${Math.round(100 * (s.prog || 0))}%"></span></div><dl>${dl}</dl></div>`;
  }).join('');
}
function progressText(r) { return r.expected ? `${(r.O ? r.O.nP : 0).toLocaleString('en-US')} of ${r.expected.toLocaleString('en-US')} reporting periods` : `${(r.O ? r.O.nP : 0).toLocaleString('en-US')} reporting periods`; }
function statusTag(r) {
  if (!r) return '<span class="tag panel">not run</span>';
  if (r.stopped) return `<span class="tag hi">stopped after ${progressText(r)}</span>`;
  if (r.R.errs.length) return `<span class="tag warn">ERROR ${r.R.errs.map(e => e.code).filter((c, i, a) => a.indexOf(c) === i).join(', ')}</span>`;
  if (r.rc) return `<span class="tag warn">code ${r.rc}</span>`;
  return '<span class="tag ok">ran</span>';
}

/* ---------------------------------------------------------------- run */
async function runOne(key, mod, inp, opts, total, st) {
  st[key] = Object.assign(st[key] || {}, { prog: 0.02 }); engCards(st);
  const r = await new KWEngine(mod).run(inp, opts, f => { st[key].prog = f; const b = $(`#eng-${key} .prog span`); if (b) b.style.width = Math.round(100 * f) + '%'; }, () => STOP);
  r.R = readRpt(r.rpt); r.O = r.out && r.out.length ? readOut(r.out) : null; r.sha = r.out && r.out.length ? await sha256(r.out) : null;
  r.expected = reportPeriods(inp);
  st[key].prog = r.stopped ? st[key].prog : 1; return r;
}
async function runAll() {
  if (BUSY || !CUR) return;
  BUSY = true; STOP = false; $('#runBtn').disabled = true; $('#stopBtn').disabled = false; $('#gateBtn').disabled = true;
  const rmode = $('#routingSel').value, inp = rmode === 'file' ? CUR.text : setRouting(CUR.text, rmode);
  const routing = routingOf(inp), split = +$('#splitSel').value, loop = $('#loopOn').checked ? 1 : 0;
  const total = durationDays(inp), withDW = $('#dwOn').checked && routing !== 'DYNWAVE';
  const meta = { id: ++RUNSEQ, name: CUR.name, routing, split, loop, withDW, inputs: inputs(), at: new Date().toISOString() };
  const st = { stock: { what: 'FLOW_ROUTING ' + routing }, kw: { what: `FLOW_ROUTING ${routing} · split ${RULES[split]} · loops ${loop ? 'iterated' : 'off'}` }, dw: { what: withDW ? ENG.dw.what : (routing === 'DYNWAVE' ? 'not needed: the file already routes DYNWAVE' : 'switched off') } };
  engCards(st); ['verdict', 'kwCard', 'chartCard', 'splitCard', 'linksCard', 'rptCard'].forEach(id => $('#' + id).classList.add('hidden'));
  RUN = null; LINKROWS = []; markStale();
  try {
    const out = { meta, inp, routing, split, loop, topo: topology(inp) };
    out.stock = await runOne('stock', MOD.stock, inp, {}, total, st);
    if (!STOP) out.kw = await runOne('kw', MOD.kw, inp, { split, loop, totalDays: total }, total, st);
    if (!STOP && withDW) out.dw = await runOne('dw', MOD.stock, setRouting(inp, 'DYNWAVE'), { totalDays: total }, total, st);
    out.wantDW = withDW;
    RUN = out; render(st); markStale();
  } catch (e) {
    const v = $('#verdict'); v.className = 'box warn'; v.innerHTML = `<p><b>The run failed inside the engine host:</b> ${esc(e.message || e)}</p>`;
  } finally {
    BUSY = false; $('#runBtn').disabled = false; $('#stopBtn').disabled = true; $('#gateBtn').disabled = false;
  }
}
$('#runBtn').addEventListener('click', runAll);
$('#stopBtn').addEventListener('click', () => { STOP = true; });

/* ---------------------------------------------------------------- render */
function render(st) {
  const R = RUN, fu = (R.kw && R.kw.O) ? UNITS[R.kw.O.flowUnits] : (R.stock && R.stock.O ? UNITS[R.stock.O.flowUnits] : '');
  for (const k of ['stock', 'kw', 'dw']) {
    const r = R[k]; if (!r) continue;
    st[k].tag = statusTag(r);
    st[k].rows = [['Routing continuity', r.R.routing != null ? r.R.routing + ' %' : '–'], ['Runoff continuity', r.R.runoff != null ? r.R.runoff + ' %' : '–'], ['Run time', r.ms + ' ms'], ['.out SHA-256', r.sha ? r.sha.slice(0, 12) : 'no output']];
  }
  engCards(st);
  // verdict. Completion comes first: a run that was stopped part-way, or never started, decides nothing,
  // and no comparison is drawn from it. (v1.0 judged a stopped swmm5-kw run by its missing error
  // lines and could print "Stock EPA refuses this network; swmm5-kw routes it.")
  const v = $('#verdict'), s = R.stock, k = R.kw; v.classList.remove('hidden');
  const sCodes = s ? s.R.errs.map(e => e.code) : [], kCodes = k ? k.R.errs.map(e => e.code) : [];
  const refused = sCodes.some(c => c === 131 || c === 133);
  const NAMES = { stock: 'Stock EPA 5.2.4', kw: 'swmm5-kw', dw: 'The dynamic-wave reference' };
  const missing = ['stock', 'kw'].concat(R.wantDW ? ['dw'] : []).filter(key => !R[key]);
  const stopped = ['stock', 'kw', 'dw'].filter(key => R[key] && R[key].stopped);
  R.complete = !stopped.length && !missing.length;
  if (!R.complete) {
    const said = stopped.map(key => `${NAMES[key]} was stopped after ${progressText(R[key])}.`)
      .concat(missing.map(key => `${NAMES[key]} did not run.`));
    v.className = 'box hi'; v.innerHTML = `<p><b>Stopped before the end.</b> ${esc(said.join(' '))}</p><p>No comparison is drawn from a partial run, and there is nothing to export. Run again and let all three finish.</p>`;
    reports(); return;
  }
  if (s && s.sha && k.sha && s.sha === k.sha && !k.R.kw) {
    v.className = 'box ok'; v.innerHTML = `<p><b>Byte for byte the same as stock.</b> This network has nothing to split or loop, so swmm5-kw wrote exactly the <code>.out</code> stock EPA 5.2.4 wrote (SHA-256 <code>${s.sha.slice(0, 16)}…</code>). That is the extension's first promise: where it has no work, it does nothing.</p>`;
  } else if (refused && !kCodes.length) {
    const why = s.R.errs.filter(e => e.code === 131 || e.code === 133).map(e => `ERROR ${e.code}: ${esc(e.text)}`).join('<br>');
    v.className = 'box ok'; v.innerHTML = `<p><b>Stock EPA refuses this network; swmm5-kw routes it.</b></p><p class="mono" style="font-size:12px">${why}</p><p>swmm5-kw ran it with routing continuity ${k.R.routing ?? '–'} %${R.dw && R.dw.R.routing != null ? `; the dynamic-wave reference gives ${R.dw.R.routing} %` : ''}.</p>`;
  } else if (kCodes.length) {
    const e = k.R.errs.map(e => `ERROR ${e.code}: ${esc(e.text)}`).join('<br>');
    const hint = kCodes.includes(133) && R.split === 0 ? ' The split rule is off, so ERROR 133 stands as in stock.' : kCodes.includes(131) && !R.loop ? ' Loop iteration is off, so ERROR 131 stands as in stock.' : kCodes.includes(133) ? ' A junction can split only when every outlet is an ordinary conduit (no pump, regulator or DUMMY link), and storage units and dividers keep their stock rules.' : '';
    v.className = 'box warn'; v.innerHTML = `<p><b>swmm5-kw stopped with an input error.</b>${hint}</p><p class="mono" style="font-size:12px">${e}</p>`;
  } else if (s && s.sha && k.sha && s.sha !== k.sha && !k.R.kw) {
    v.className = 'box warn'; v.innerHTML = '<p><b>The outputs differ, and swmm5-kw reports no split or loop.</b> That should not happen. Please keep this model: it is a counterexample to the null-effect gate.</p>';
  } else {
    v.className = 'box panel'; v.innerHTML = '<p><b>swmm5-kw split or looped this network.</b> Stock ran it too, so the difference below is the extension at work.</p>';
  }
  // KW card
  const kw = k && k.R.kw, stats = k && k.stats;
  if (kw || (stats && (stats[0] || stats[1]))) {
    $('#kwCard').classList.remove('hidden');
    const tile = (n, l) => `<div class="tile"><div class="n">${n}</div><div class="l">${l}</div></div>`;
    $('#kwTiles').innerHTML = [
      tile(stats ? stats[0] : (kw ? kw.split.length : 0), 'split junctions'),
      tile(stats ? stats[1] : (kw ? kw.loops.length : 0), 'loop-closing links'),
      tile(stats ? fmt(stats[2], 0) : '–', 'allocations made'),
      tile(stats ? fmt(stats[3], 1) + ' ' + fu : '–', 'largest allocation imbalance'),
      tile(stats && stats[4] ? fmt(stats[5], 2) : '–', 'mean sweeps per looped step'),
      tile(stats && stats[4] ? fmt(stats[6], 0) : '–', 'most sweeps in one step'),
      tile(stats && stats[4] ? fmt(stats[7], 0) : '–', 'steps that hit the 60-sweep cap'),
      tile(stats && stats[0] && R.split === 1 ? fmt(stats[9], 1) : '–', 'mean HEAD bisection iterations'),
    ].join('');
    const ids = a => a.length ? `<div class="idlist">${a.slice(0, 200).map(x => `<code>${esc(x)}</code>`).join('')}${a.length > 200 ? `<span class="faint">and ${a.length - 200} more</span>` : ''}</div>` : '<span class="faint">none</span>';
    $('#kwLists').innerHTML = kw ? `<h3>Split junctions (rule ${esc(kw.rule)})</h3>${ids(kw.split)}<h3>Loop-closing links</h3>${ids(kw.loops)}${k.R.loopLine ? `<p class="faint" style="margin-top:8px">${esc(k.R.loopLine)}</p>` : ''}` : '';
  }
  splitTable(); linksTable(); fillLinkSel(); drawChart(); reports();
}

/* Peak statistics of one series. null when the run wrote no series for the link (a refused run, a
   link it never reached), so a missing value stays missing. (v1.0 started a signed maximum at
   -Infinity, exported that for empty series, and showed 0 for a pipe that only ran backwards.) */
function flowStats(run, id) {
  const s = seriesOf(run, id); if (!s || !s.length) return null;
  let max = -Infinity, min = Infinity; for (const x of s) { if (x > max) max = x; if (x < min) min = x; }
  const abs = Math.max(Math.abs(max), Math.abs(min));
  return { max, min, abs, reverses: min < -Math.max(1e-6, 1e-3 * abs) };
}

function seriesOf(run, id) { if (!run || !run.O) return null; const i = run.O.linkIx.get(id.toUpperCase()); return i == null ? null : linkSeries(run.O, i, 0); }
function splitInfo() {
  const R = RUN, kw = R.kw && R.kw.R.kw; if (!kw || !kw.split.length) return [];
  const outl = {}; for (const [id, [a, b, kind]] of Object.entries(R.topo)) { (outl[a.toUpperCase()] = outl[a.toUpperCase()] || []).push(id); }
  return kw.split.map(j => ({ j, outs: (outl[j.toUpperCase()] || []) }));
}
function shareAtPeak(run, outs) {
  const S = outs.map(id => seriesOf(run, id)); if (S.some(x => !x)) return null;
  let best = -1, bi = 0; for (let p = 0; p < S[0].length; p++) { let t = 0; for (const s of S) t += Math.max(0, s[p]); if (t > best) { best = t; bi = p; } }
  return { total: best, share: S.map(s => best > 0 ? Math.max(0, s[bi]) / best : null), stats: outs.map(id => flowStats(run, id)) };
}
function splitTable() {
  const info = splitInfo(); if (!info.length) return;
  $('#splitCard').classList.remove('hidden');
  const R = RUN, rows = [];
  for (const { j, outs } of info.slice(0, 60)) {
    const a = shareAtPeak(R.kw, outs), b = R.dw ? shareAtPeak(R.dw, outs) : null;
    const pk = (x, i) => { const q = x && x.stats[i]; return q ? fmt(q.abs, 2) + (q.reverses ? ` <span class="tag hi" title="runs backwards: minimum ${fmt(q.min, 3)}">reverses</span>` : '') : '–'; };
    outs.forEach((id, i) => rows.push(`<tr><td>${i ? '' : `<b>${esc(j)}</b>`}</td><td>${esc(id)}</td><td class="num">${pk(a, i)}</td><td class="num">${pk(b, i)}</td><td class="num">${a && a.share[i] != null ? (100 * a.share[i]).toFixed(1) + '%' : '–'}</td><td class="num">${b && b.share[i] != null ? (100 * b.share[i]).toFixed(1) + '%' : '–'}</td></tr>`));
  }
  const fu = R.kw.O ? UNITS[R.kw.O.flowUnits] : '';
  $('#splitTable').innerHTML = `<thead><tr><th>Junction</th><th>Outlet</th><th class="num">|Peak|, swmm5-kw (${fu})</th><th class="num">|Peak|, DYNWAVE</th><th class="num">Share, swmm5-kw</th><th class="num">Share, DYNWAVE</th></tr></thead><tbody>${rows.join('')}</tbody>`;
}
let LINKROWS = [];
function linksTable() {
  const R = RUN, base = (R.kw && R.kw.O) || (R.stock && R.stock.O); if (!base) return;
  $('#linksCard').classList.remove('hidden');
  const fu = UNITS[base.flowUnits];
  LINKROWS = base.links.map(id => {
    const k = flowStats(R.kw, id), d = flowStats(R.dw, id), s = flowStats(R.stock, id);
    const rev = [['swmm5-kw', k], ['DYNWAVE', d], ['stock', s]].filter(x => x[1] && x[1].reverses).map(x => x[0]);
    return { id, k, d, s, rev, diff: (k && d && d.abs > 1e-6) ? 100 * (k.abs - d.abs) / d.abs : null };
  });
  LINKROWS.sort((a, b) => (b.rev.length - a.rev.length) || (Math.abs(b.diff ?? 0) - Math.abs(a.diff ?? 0)));
  const mx = q => q ? fmt(q.max, 3) : '–', mn = q => q ? (q.reverses ? `<b>${fmt(q.min, 3)}</b>` : fmt(q.min, 3)) : '–';
  $('#linksTable').innerHTML = `<thead><tr><th>Link</th><th>Reverses in</th><th class="num">swmm5-kw max (${fu})</th><th class="num">swmm5-kw min</th><th class="num">DYNWAVE max</th><th class="num">DYNWAVE min</th><th class="num">Stock max</th><th class="num">Stock min</th><th class="num">|Peak| swmm5-kw vs DYNWAVE</th></tr></thead><tbody>` +
    LINKROWS.slice(0, 500).map(r => `<tr><td>${esc(r.id)}</td><td>${r.rev.length ? r.rev.map(x => `<span class="tag hi">${x}</span>`).join(' ') : ''}</td><td class="num">${mx(r.k)}</td><td class="num">${mn(r.k)}</td><td class="num">${mx(r.d)}</td><td class="num">${mn(r.d)}</td><td class="num">${mx(r.s)}</td><td class="num">${mn(r.s)}</td><td class="num">${r.diff == null ? '–' : (r.diff > 0 ? '+' : '') + r.diff.toFixed(1) + '%'}</td></tr>`).join('') +
    (LINKROWS.length > 500 ? `<tr><td colspan="9" class="muted">${LINKROWS.length - 500} more in the CSV export</td></tr>` : '') + '</tbody>';
}
function fillLinkSel() {
  const R = RUN, base = (R.kw && R.kw.O) || (R.stock && R.stock.O), sel = $('#linkSel'); if (!base) return;
  const info = splitInfo(); let pick = info.length ? info[0].outs.slice(0, 4) : [];
  if (!pick.length && R.kw && R.kw.R.kw && R.kw.R.kw.loops.length) pick = R.kw.R.kw.loops.slice(0, 2);
  if (!pick.length) pick = LINKROWS.slice(0, 2).map(r => r.id);
  const pickU = new Set(pick.map(x => x.toUpperCase()));
  sel.innerHTML = base.links.slice(0, 3000).map(id => `<option ${pickU.has(id.toUpperCase()) ? 'selected' : ''}>${esc(id)}</option>`).join('');
  $('#chartCard').classList.remove('hidden');
}
$('#linkSel').addEventListener('change', () => drawChart());
function cssv(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function drawChart() {
  const R = RUN; if (!R) return; const svg = $('#chart'), W = 760, H = 320, L = 58, Rm = 14, T = 14, B = 40;
  const ids = [...$('#linkSel').selectedOptions].map(o => o.value).slice(0, 6);
  const base = (R.kw && R.kw.O) || (R.stock && R.stock.O); if (!base || !ids.length) { svg.innerHTML = ''; return; }
  const pal = ['--f-a', '--f-b', '--f-c', '--f-d', '--f-e', '--f-f'].map(cssv), ink = cssv('--f-dim'), grid = cssv('--f-line');
  const runs = [['kw', ''], ['dw', '7 5'], ['stock', '2 4']];
  const series = []; let ymax = 0, ymin = 0;
  ids.forEach((id, i) => runs.forEach(([k, dash]) => { const s = seriesOf(R[k], id); if (!s) return; for (const x of s) { if (x > ymax) ymax = x; if (x < ymin) ymin = x; } series.push({ id, k, dash, s, c: pal[i % pal.length] }); }));
  if (ymax === ymin) ymax = ymin + 1;
  { const span = ymax - ymin, st = Math.pow(10, Math.floor(Math.log10(span / 5))), e = span / 5 / st, step = st * (e >= 5 ? 10 : e >= 2 ? 5 : e >= 1 ? 2 : 1); ymax = Math.ceil((ymax + 0.02 * span) / step) * step; if (ymin < 0) ymin = Math.floor((ymin - 0.02 * span) / step) * step; }
  // x is time: each sample at its recorded hour, the axis from the report start to the last sample
  const tEnd = Math.max(...series.map(s => { const O = R[s.k].O; return O.hours[O.nP - 1] || 0; }), 1e-9);
  const X = t => L + (W - L - Rm) * t / tEnd, Y = y => T + (H - T - B) * (1 - (y - ymin) / (ymax - ymin));
  const nice = (lo, hi, n) => { const span = hi - lo, st = Math.pow(10, Math.floor(Math.log10(span / n))), e = span / n / st, step = st * (e >= 5 ? 10 : e >= 2 ? 5 : e >= 1 ? 2 : 1); const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10)); return out; };
  let g = '';
  for (const yv of nice(ymin, ymax, 5)) g += `<line x1="${L}" x2="${W - Rm}" y1="${Y(yv)}" y2="${Y(yv)}" stroke="${grid}" stroke-width="1"/><text x="${L - 6}" y="${Y(yv) + 4}" fill="${ink}" font-size="11" text-anchor="end">${+yv.toPrecision(4)}</text>`;
  for (const hv of nice(0, tEnd, 6)) g += `<text x="${X(hv).toFixed(1)}" y="${H - B + 16}" fill="${ink}" font-size="11" text-anchor="middle">${+hv.toPrecision(4)}</text>`;
  g += `<text x="${(L + W - Rm) / 2}" y="${H - 6}" fill="${ink}" font-size="11" text-anchor="middle">hours from the start of the report</text><text x="14" y="${(T + H - B) / 2}" fill="${ink}" font-size="11" text-anchor="middle" transform="rotate(-90 14 ${(T + H - B) / 2})">flow (${UNITS[base.flowUnits]})</text>`;
  for (const s of series) { const hrs = R[s.k].O.hours, stride = Math.max(1, Math.floor(s.s.length / 1500)); let d = ''; for (let p = 0; p < s.s.length; p += stride) d += (d ? 'L' : 'M') + X(hrs[p]).toFixed(1) + ' ' + Y(s.s[p]).toFixed(1); g += `<path d="${d}" fill="none" stroke="${s.c}" stroke-width="${s.k === 'kw' ? 2.2 : 1.6}" ${s.dash ? `stroke-dasharray="${s.dash}"` : ''} stroke-linejoin="round"/>`; }
  svg.innerHTML = g;
  $('#chartTitle').textContent = ids.length > 1 ? 'Flow in ' + ids.join(', ') : 'Flow in ' + ids[0];
  $('#chartLegend').innerHTML = ids.map((id, i) => `<span><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke="${pal[i % pal.length]}" stroke-width="3"/></svg>${esc(id)}</span>`).join('') +
    `<span><svg width="26" height="8"><line x1="0" x2="26" y1="4" y2="4" stroke="${ink}" stroke-width="2"/></svg>swmm5-kw</span><span><svg width="26" height="8"><line x1="0" x2="26" y1="4" y2="4" stroke="${ink}" stroke-width="2" stroke-dasharray="7 5"/></svg>DYNWAVE</span><span><svg width="26" height="8"><line x1="0" x2="26" y1="4" y2="4" stroke="${ink}" stroke-width="2" stroke-dasharray="2 4"/></svg>stock</span>`;
}
function reports() {
  const R = RUN; $('#rptCard').classList.remove('hidden');
  const have = ['kw', 'stock', 'dw'].filter(k => R[k]);
  if (!have.includes(RPTSEL)) RPTSEL = have[0];
  $('#rptSeg').innerHTML = have.map(k => `<button type="button" data-k="${k}" class="${k === RPTSEL ? 'on' : ''}">${k === 'kw' ? 'swmm5-kw' : k === 'stock' ? 'Stock' : 'DYNWAVE'}</button>`).join('');
  $$('#rptSeg button').forEach(b => b.addEventListener('click', () => { RPTSEL = b.dataset.k; reports(); }));
  const t = R[RPTSEL].rpt; $('#rptPre').textContent = t.length > 400000 ? t.slice(0, 400000) + '\n… (truncated for display)' : t;
}

/* ---------------------------------------------------------------- export */
$('#exportBtn').addEventListener('click', () => {
  if (!RUN) { toast('Run a model first.'); return; }
  if (!RUN.complete) { toast('The last run was stopped before the end: nothing to export.'); return; }
  if (!LINKROWS.length) { toast('The last run wrote no link results.'); return; }
  const m = RUN.meta, num = x => x == null || !isFinite(x) ? '' : String(+x.toPrecision(7));
  const lines = [`# swmm5-kw run ${m.id}: ${m.name}, FLOW_ROUTING ${m.routing}, split ${RULES[m.split]}, loops ${m.loop ? 'iterated' : 'off'}, DYNWAVE reference ${RUN.dw ? 'run' : 'not run'}, started ${m.at}`,
    '# flows in ' + UNITS[((RUN.kw && RUN.kw.O) || (RUN.stock && RUN.stock.O)).flowUnits] + '; max and min are signed, abs_peak = max(|max|, |min|); blank = that run wrote no series for the link',
    'link,kw_max,kw_min,kw_abs_peak,dw_max,dw_min,dw_abs_peak,stock_max,stock_min,stock_abs_peak,pct_diff_abs_peak_kw_vs_dw,reverses_in'];
  const q = st => st ? [num(st.max), num(st.min), num(st.abs)] : ['', '', ''];
  for (const r of LINKROWS) lines.push([r.id, ...q(r.k), ...q(r.d), ...q(r.s), r.diff == null ? '' : r.diff.toFixed(3), r.rev.join(' ')].join(','));
  const file = m.name.replace(/\.inp$/i, '') + '_swmm5kw_peaks.csv';
  save(file, lines.join('\n') + '\n', 'text/csv');
  if (!sameInputs(m.inputs, inputs())) toast(`Saved run ${m.id} (${m.name}), not the inputs now selected`);
});

/* ---------------------------------------------------------------- in-browser gates */
async function runGates() {
  if (BUSY) return; BUSY = true; $('#gateBtn').disabled = true; $('#runBtn').disabled = true;
  const rows = [], put = () => { $('#gateTable').innerHTML = '<thead><tr><th>Network</th><th>Routing</th><th>Stock</th><th>Off (0/0) = stock</th><th>HEAD · CAPACITY · AREA</th><th class="num">Max imbalance</th></tr></thead><tbody>' + rows.join('') + '</tbody>'; };
  let pass = 0, fail = 0;
  try {
    for (const m of MODELS) {
      const st = await new KWEngine(MOD.stock).run(m.text, {}); const sSha = await sha256(st.out), sR = readRpt(st.rpt);
      const off = await new KWEngine(MOD.kw).run(m.text, { split: 0, loop: 0 }); const oSha = await sha256(off.out);
      const offSame = sSha === oSha && st.rpt.replace(/^.*(Analysis begun|Analysis ended|Total elapsed).*$/gm, '') === off.rpt.replace(/^.*(Analysis begun|Analysis ended|Total elapsed).*$/gm, '');
      const refused = sR.errs.some(e => e.code === 131 || e.code === 133);
      const res = []; let imb = 0, ok = offSame;
      for (const sp of [1, 2, 3]) {
        const r = await new KWEngine(MOD.kw).run(m.text, { split: sp, loop: 1 }); const R = readRpt(r.rpt), sha = await sha256(r.out);
        imb = Math.max(imb, r.stats ? r.stats[3] : 0);
        if (refused) { const good = !R.errs.length && R.routing != null; res.push(good ? 'runs' : 'ERROR'); ok = ok && good; }
        else { const same = sha === sSha; res.push(same ? 'same bytes' : 'DIFFERS'); ok = ok && same; }
      }
      ok = ok && imb < 1e-9; ok ? pass++ : fail++;
      const codes = sR.errs.map(e => e.code).filter((c, i, a) => a.indexOf(c) === i);
      rows.push(`<tr><td>${esc(m.name)}</td><td>${routingOf(m.text)}</td><td>${codes.length ? `<span class="tag hi">ERROR ${codes.join(', ')}</span>` : '<span class="tag panel">ran</span>'}</td><td>${offSame ? '<span class="tag ok">identical</span>' : '<span class="tag warn">differs</span>'}</td><td>${res.map(x => `<span class="tag ${/runs|same/.test(x) ? 'ok' : 'warn'}">${x}</span>`).join(' ')}</td><td class="num">${imb.toExponential(1)}</td></tr>`);
      put(); $('#gateNote').textContent = `${pass + fail} of ${MODELS.length} networks`;
    }
    $('#gateNote').textContent = fail ? `${fail} of ${MODELS.length} networks failed a check` : `all ${MODELS.length} networks pass, ${MODELS.length * 4 + MODELS.length} runs`;
  } catch (e) { $('#gateNote').textContent = 'stopped: ' + (e.message || e); }
  finally { BUSY = false; $('#gateBtn').disabled = false; $('#runBtn').disabled = false; }
}
$('#gateBtn').addEventListener('click', runGates);
function verifyTables() {
  const G = RESULTS.gates || [];
  $('#nativeGates').innerHTML = '<thead><tr><th>Gate</th><th>Result</th></tr></thead><tbody>' + G.map(g => `<tr><td>${esc(g[0])}</td><td>${esc(g[1])}</td></tr>`).join('') + '</tbody>';
  const C = RESULTS.corpus;
  if (C) {
    $('#corpusBox').innerHTML = `<p>${esc(C.summary)}</p><div class="tablewrap"><table class="t"><thead><tr><th>Pass</th><th class="num">Models</th><th class="num">Identical to stock</th><th class="num">Refused by stock, run by swmm5-kw</th><th class="num">Stock crashes, same crash</th><th class="num">Different</th><th class="num">Inconclusive</th></tr></thead><tbody>` +
      C.rows.map(r => `<tr><td>${esc(r[0])}</td>${r.slice(1).map(x => `<td class="num">${esc(x)}</td>`).join('')}</tr>`).join('') + `</tbody></table></div>` + (C.note ? `<p class="faint" style="margin-top:6px">${esc(C.note)}</p>` : '') + (C.whatif ? `<div class="box panel" style="margin-top:10px"><p>${esc(C.whatif)}</p></div>` : '');
  } else $('#corpusBox').innerHTML = '<p class="muted">The corpus gate results are in the repository\'s <code>results/</code>.</p>';
  $('#provTable').innerHTML = '<thead><tr><th>File</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>' + (RESULTS.engines || []).map(e => `<tr><td>${esc(e[0])}</td><td class="num">${esc(e[1])}</td><td><code style="font-size:10.5px">${esc(e[2])}</code></td></tr>`).join('') + '</tbody>';
}

/* ---------------------------------------------------------------- doc table of contents */
function buildToc() {
  const hs = $$('#essay h2'); $('#toc').innerHTML = hs.map((h, i) => { h.id = h.id || 'sec' + i; return `<a href="#${h.id}">${esc(h.textContent)}</a>`; }).join('');
  $$('#toc a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); const t = document.getElementById(a.getAttribute('href').slice(1)); if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
}

/* ---------------------------------------------------------------- help and GIF */
function openWelcome() { $('#welcome').hidden = false; $('#welcomeClose').focus(); }
$('#helpBtn').addEventListener('click', openWelcome);
$('#welcomeClose').addEventListener('click', () => { $('#welcome').hidden = true; try { localStorage.setItem('swmm5kw_seen', '1'); } catch (e) {} });
document.addEventListener('keydown', e => { if (e.key === 'Escape') $('#welcome').hidden = true; });
let REC = null;
function loadScript(src) { return new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = rej; document.head.appendChild(s); }); }
$('#gifBtn').addEventListener('click', async () => {
  if (REC) { REC.stop = true; return; }
  try { if (!window.html2canvas) await loadScript('https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js'); }
  catch (e) { toast('The capture library could not load.'); return; }
  REC = { frames: [], stop: false }; $('#gifBtn').textContent = 'Recording… click to stop';
  if (!RUN && !BUSY) { showView('run'); await runAll(); }
  const steps = [['run', 'Run: stock refuses, swmm5-kw splits, dynamic wave checks'], ['verify', 'Verify: the gates, natively and in this browser'], ['doc', 'Doc: how a junction shares its water']];
  const bg = getComputedStyle(document.body).backgroundColor, capbar = cssv('--capbar'), capink = cssv('--capink');
  for (const [v, cap] of steps) {
    if (REC.stop) break; showView(v); scrollTo(0, 0); await new Promise(r => setTimeout(r, 400));
    for (let k = 0; k < 4 && !REC.stop; k++) {
      const c = await html2canvas($('#app'), { backgroundColor: bg, scale: 0.6, logging: false, height: Math.min($('#app').scrollHeight, 900), windowHeight: 900 });
      const ctx = c.getContext('2d'); ctx.fillStyle = capbar; ctx.fillRect(0, c.height - 30, c.width, 30);
      ctx.fillStyle = capink; ctx.font = '15px sans-serif'; ctx.fillText(cap, 12, c.height - 10);
      REC.frames.push(c); await new Promise(r => setTimeout(r, 350));
    }
  }
  const frames = REC.frames; REC = null; $('#gifBtn').textContent = 'Make a GIF'; if (!frames.length) return;
  let blob = null, ext = 'gif';
  try {
    if (!window.GIF) await loadScript('https://cdnjs.cloudflare.com/ajax/libs/gif.js/0.2.0/gif.js');
    const wurl = URL.createObjectURL(new Blob(["importScripts('https://cdnjs.cloudflare.com/ajax/libs/gif.js/0.2.0/gif.worker.js');"], { type: 'text/javascript' }));
    blob = await new Promise((res, rej) => { const g = new GIF({ workers: 2, quality: 12, workerScript: wurl, width: frames[0].width, height: frames[0].height }); frames.forEach(f => g.addFrame(f, { delay: 700 })); g.on('finished', res); g.on('abort', () => rej(new Error('aborted'))); setTimeout(() => rej(new Error('timeout')), 60000); g.render(); });
  } catch (e) {
    try {
      ext = 'webm'; const cv = document.createElement('canvas'); cv.width = frames[0].width; cv.height = frames[0].height;
      const cx = cv.getContext('2d'), str = cv.captureStream(4), mr = new MediaRecorder(str, { mimeType: 'video/webm' }), ch = [];
      mr.ondataavailable = ev => ch.push(ev.data);
      blob = await new Promise(res => { mr.onstop = () => res(new Blob(ch, { type: 'video/webm' })); mr.start(); let i = 0; const nx = () => { if (i >= frames.length) return mr.stop(); cx.drawImage(frames[i++], 0, 0); setTimeout(nx, 700); }; nx(); });
    } catch (e2) { toast('This browser cannot encode the recording.'); return; }
  }
  save('swmm5-kw-walkthrough.' + ext, blob);
});

/* ---------------------------------------------------------------- boot */
(async function init() {
  let pref = 'dark'; try { const v = localStorage.getItem('swmm5kw_theme'); if (v === 'light' || v === 'auto' || v === 'dark') pref = v; } catch (e) {}
  applyTheme(pref);
  const h = location.hash.slice(1); if (h && $('#view-' + h)) showView(h);
  let seen = false; try { seen = localStorage.getItem('swmm5kw_seen') === '1'; } catch (e) {}
  if (!seen) openWelcome();
  fillModels(); verifyTables(); buildToc();
  try {
    MOD.kw = await WebAssembly.compile(b64bytes('#wasm-kw'));
    MOD.stock = await WebAssembly.compile(b64bytes('#wasm-stock'));
    $('#runBtn').disabled = false; $('#runBtn').textContent = 'Run the three'; $('#gateBtn').disabled = false;
    engCards({});
  } catch (e) {
    $('#runBtn').textContent = 'Engines unavailable';
    const v = $('#verdict'); v.className = 'box warn'; v.classList.remove('hidden');
    v.innerHTML = `<p><b>This page cannot start WebAssembly here</b> (${esc(e.message || e)}). A content-security policy without <code>wasm-unsafe-eval</code> does this. Open the file directly in a browser, or run <code>tools/build.sh</code> and the native <code>kwswmm</code>.</p>`;
  }
})();
