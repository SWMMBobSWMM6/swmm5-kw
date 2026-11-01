// The app findings of the second outside review of swmm5-kw v1.0 (2026-10-31), as browser checks of the
// right behaviour. They fail on the v1.0 page and pass on v1.1. Written on the parallel review branch
// (claude/kw-v1.1-review-fixes) and adapted to main's page: #staleBar, the min_dynwave column, and the
// "Runs backwards in" column.
//   node tests/app/review2.test.js [--page=path/to/swmm5-kw.html]
// Needs Playwright with Chromium (require('playwright')). Writes nothing unless every check passes on dist/.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), os = require('os');
const R = path.join(__dirname, '..', '..');
const arg = process.argv.find(a => a.startsWith('--page='));
const PAGE = arg ? path.resolve(arg.slice(7)) : path.join(R, 'dist', 'swmm5-kw.html');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'kwapp-'));
const results = [];
const check = (ok, msg) => { results.push([!!ok, msg]); console.log((ok ? '  ok   ' : '  FAIL ') + msg); };
const model = n => fs.readFileSync(path.join(R, 'models', n), 'utf8');
const setOpt = (txt, key, val) => txt.replace(new RegExp('^' + key + '\\s+\\S+', 'm'), key.padEnd(21) + val);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } });
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  await page.route(/^https?:\/\//, r => r.abort());                       // offline: fonts and CDNs
  await page.addInitScript(() => {
    try { localStorage.setItem('swmm5kw_seen', '1'); } catch (e) {}
    window.__saved = []; const blobs = new Map(), cou = URL.createObjectURL.bind(URL);
    URL.createObjectURL = b => { const u = cou(b); blobs.set(u, b); return u; };
    HTMLAnchorElement.prototype.click = function () { const b = blobs.get(this.href); if (b && this.download) b.text().then(t => window.__saved.push({ name: this.download, text: t })); };
  });
  await page.goto('file://' + PAGE);
  await page.waitForFunction(() => !document.getElementById('runBtn').disabled, null, { timeout: 60000 });
  const version = await page.evaluate(() => (document.querySelector('.pill') || {}).textContent || '');
  console.log('page:', version.trim());
  const pick = async name => { await page.selectOption('#modelSel', { label: (await page.$$eval('#modelSel option', (os, n) => os.find(o => o.textContent.startsWith(n)).textContent, name)) }); };
  const runAndWait = async () => {
    await page.click('#runBtn');
    await page.waitForFunction(() => !document.getElementById('runBtn').disabled && !document.getElementById('verdict').classList.contains('hidden'), null, { timeout: 120000 });
    await page.waitForTimeout(200);
  };
  const exportCsv = async () => {   // the file this click saved, or null if it saved none
    const n = await page.evaluate(() => window.__saved.length); await page.click('#exportBtn');
    await page.waitForFunction(k => window.__saved.length > k, n, { timeout: 3000 }).catch(() => {});
    return page.evaluate(k => window.__saved.length > k ? window.__saved[window.__saved.length - 1] : null, n);
  };
  const loadInp = async (name, text) => { const f = path.join(TMP, name); fs.writeFileSync(f, text); await page.setInputFiles('#fileIn', f); await page.waitForTimeout(300); };

  // 2. Results keep the identity of the run that made them.
  await pick('split.inp'); await runAndWait();
  await pick('diamond.inp');
  let csv = await exportCsv();
  const body = csv ? csv.text : '', hasSplitLinks = /^CB,/m.test(body) && /^CA,/m.test(body);
  const banner = await page.evaluate(() => { const e = document.getElementById('staleBar'); return e && !e.hidden && !e.classList.contains('hidden') ? e.textContent : ''; });
  check(csv && hasSplitLinks && /^split/.test(csv.name) && /split\.inp/.test(body), '2 export after switching models is named and labelled for the run it holds: ' + (csv ? csv.name : 'nothing saved'));
  check(/split\.inp/.test(banner) && /out of date|run the three/i.test(banner), '2 the stale results say so once the model changes: "' + banner.slice(0, 90) + '"');

  // 4a. A run with no output exports blank values, not -Infinity.
  check(!/Infinity/.test(body), '4 no -Infinity in the CSV for the stock run that ERROR 133 stopped');

  // 4b. Reversed flow is shown, not hidden by the signed maximum.
  await pick('loopactive_dynwave.inp');
  await page.selectOption('#routingSel', 'KINWAVE');
  await runAndWait();
  csv = await exportCsv();
  const row = csv ? csv.text.split('\n').find(l => l.startsWith('R1,')) : null, head = csv ? csv.text.split('\n').find(l => l.startsWith('link,')) : '';
  const col = (h, r, name) => { const i = h.split(',').indexOf(name); return i < 0 || !r ? null : r.split(',')[i]; };
  const dwMin = row ? parseFloat(col(head, row, 'min_dynwave')) : NaN;
  check(dwMin < -3, '4 R1 in the relief loop: DYNWAVE minimum exported (' + (row ? col(head, row, 'min_dynwave') : 'no column') + ' cfs; the review saw -3.33956)');
  const tableR1 = await page.evaluate(() => { const tr = [...document.querySelectorAll('#linksTable tbody tr')].find(t => t.cells[0] && t.cells[0].textContent.trim() === 'R1'); return tr ? tr.textContent : ''; });
  check(/[-−]3\.3/.test(tableR1) && /revers|backwards/i.test(tableR1 + (await page.textContent('#linksTable thead'))), '4 the links table shows R1\'s negative minimum and flags the reversal: "' + tableR1.replace(/\s+/g, ' ').slice(0, 90) + '"');

  // 5. Samples sit at their recorded times; every tick is inside the chart.
  const hourly = setOpt(setOpt(model('split.inp'), 'REPORT_STEP', '01:00:00'), 'END_TIME', '06:00:00');
  await page.selectOption('#routingSel', 'file');
  await loadInp('split_hourly.inp', hourly); await runAndWait();
  const ax = await page.evaluate(() => {
    const svg = document.getElementById('chart'), p = svg.querySelector('path'); if (!p) return null;
    const m = /M\s*([\d.]+)/.exec(p.getAttribute('d'));
    const ticks = [...svg.querySelectorAll('text')].filter(t => +t.getAttribute('y') > 270 && /^\d+(\.\d+)?$/.test(t.textContent)).map(t => [t.textContent, +t.getAttribute('x')]);
    return { first: +m[1], ticks };
  });
  const L = 58, Wp = 760 - 14, x1 = L + (Wp - L) * (1 / 6);
  check(ax && Math.abs(ax.first - x1) < 1.5, '5 hourly reporting: the first sample (hour 1) is drawn at hour 1 (x ' + (ax ? ax.first.toFixed(1) : '?') + ', want ' + x1.toFixed(1) + ')');
  const six = ax && ax.ticks.find(t => t[0] === '6');
  check(six && six[1] <= Wp + 0.5, '5 six periods: the 6-hour tick is inside the chart (x ' + (six ? six[1].toFixed(1) : 'missing') + ', right edge ' + Wp + ')');

  // 3. A stopped run never gets a success headline.
  const long = setOpt(setOpt(model('split.inp'), 'END_DATE', '01/31/2026'), 'END_TIME', '06:00:00');
  await loadInp('split_30days.inp', long);
  await page.click('#runBtn');
  await page.waitForFunction(() => { const s = document.querySelector('#eng-kw .prog span'); return s && parseFloat(s.style.width) >= 2; }, null, { timeout: 120000 });
  await page.click('#stopBtn');
  await page.waitForFunction(() => !document.getElementById('runBtn').disabled, null, { timeout: 60000 });
  await page.waitForTimeout(300);
  const v3 = await page.evaluate(() => { const v = document.getElementById('verdict'); return { cls: v.className, text: v.textContent }; });
  const comparisons = await page.evaluate(() => ['splitCard', 'linksCard', 'chartCard'].filter(id => !document.getElementById(id).classList.contains('hidden')));
  check(!/routes it/.test(v3.text) && !/\bok\b/.test(v3.cls) && /stopped/i.test(v3.text), '3 swmm5-kw stopped part-way: the verdict says stopped, not success: "' + v3.text.replace(/\s+/g, ' ').slice(0, 100) + '"');
  check(/of [\d,]+ reporting periods/.test(v3.text), '3 the stopped verdict says how far the run got');
  check(!comparisons.length, '3 no hydraulic comparison is drawn from the partial run (shown: ' + (comparisons.join(', ') || 'none') + ')');
  csv = await exportCsv();
  check(!csv, '3 a stopped run cannot be exported as results' + (csv ? ' (saved ' + csv.name + ')' : ''));

  check(!errors.length, 'no page errors' + (errors.length ? ': ' + errors[0].slice(0, 120) : ''));
  await browser.close();
  const pass = results.filter(r => r[0]).length;
  console.log(`\n${pass} passed, ${results.length - pass} failed (${version.trim()})`);
  if (!arg && pass === results.length) fs.writeFileSync(path.join(R, 'results', 'app_review2.json'), JSON.stringify({ checks: results.length, version: version.trim(), date: new Date().toISOString().slice(0, 10) }, null, 1));
  process.exit(results.length - pass ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
