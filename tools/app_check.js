// Replays the five app findings of the outside review of 31 October 2026 against dist/swmm5-kw.html
// in Chromium (Playwright), plus the in-browser gates. Usage: node tools/app_check.js
// Writes its two test inputs (split.inp at 30 days / 1-minute reporting, and 6 hours / hourly) to a
// temporary folder; prints one line per scenario. See lessons/a-result-carries-its-run.md.
const { chromium } = require('playwright');
const fs = require('fs'), os = require('os'), path = require('path');
const R = path.resolve(__dirname, '..'), D = fs.mkdtempSync(path.join(os.tmpdir(), 'swmm5kw-app-'));
{ const t = fs.readFileSync(path.join(R, 'models', 'split.inp'), 'utf8');
  const opt = (s, k, v) => new RegExp('^' + k + '\\s', 'mi').test(s) ? s.replace(new RegExp('^(' + k + '\\s+)\\S+', 'mi'), '$1' + v) : s.replace(/^\[OPTIONS\]\s*$/mi, '[OPTIONS]\n' + k + ' ' + v);
  fs.writeFileSync(path.join(D, 'split_30day.inp'), opt(opt(t, 'END_DATE', '01/31/2026'), 'REPORT_STEP', '00:01:00'));
  const sd = /^START_DATE\s+(\S+)/mi.exec(t)[1];
  fs.writeFileSync(path.join(D, 'split_6h_hourly.inp'), opt(opt(opt(t, 'END_DATE', sd), 'END_TIME', '06:00:00'), 'REPORT_STEP', '01:00:00')); }
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1360, height: 1000 }, acceptDownloads: true });
  const pg = await ctx.newPage(); const errs = [];
  pg.on('pageerror', e => errs.push('PAGEERROR ' + e.message));
  await pg.goto('file://' + path.join(R, 'dist', 'swmm5-kw.html')); await pg.waitForTimeout(400);
  await pg.click('#welcomeClose');
  await pg.waitForFunction(() => !document.querySelector('#runBtn').disabled, null, { timeout: 30000 });
  const runDone = () => pg.waitForFunction(() => !document.querySelector('#runBtn').disabled && !document.querySelector('#verdict').classList.contains('hidden'), null, { timeout: 120000 });
  const pick = async label => { const v = await pg.$$eval('#modelSel option', (os, l) => (os.find(o => o.textContent.startsWith(l)) || {}).value, label); await pg.selectOption('#modelSel', v); };
  const exportCsv = async () => { const [dl] = await Promise.all([pg.waitForEvent('download'), pg.click('#exportBtn')]); const p = D + '/' + dl.suggestedFilename(); await dl.saveAs(p); return [dl.suggestedFilename(), fs.readFileSync(p, 'utf8')]; };

  // 2 + 4a: split.inp, export; then pick diamond.inp without rerunning
  await pick('split.inp'); await pg.click('#runBtn'); await runDone();
  let [fn, csv] = await exportCsv();
  console.log('[4a] split.inp export:', fn, '| contains Infinity:', /Infinity/.test(csv), '| first line:', csv.split('\n')[0].slice(0, 110));
  console.log('      stock columns for CA:', csv.split('\n').find(l => l.startsWith('CA,')));
  await pick('diamond.inp'); await pg.waitForTimeout(100);
  const stale = await pg.$eval('#staleBar', e => !e.classList.contains('hidden') && e.textContent);
  [fn, csv] = await exportCsv();
  console.log('[2] after picking diamond.inp: stale banner:', stale ? stale.slice(0, 170) : 'NOT SHOWN');
  console.log('    export file:', fn, '| rows for CA/CB (split.inp links):', csv.split('\n').filter(l => /^C[AB],/.test(l)).length);

  // 4b: loopactive.inp, R1 reverses under DYNWAVE
  await pick('loopactive.inp'); await pg.click('#runBtn'); await runDone();
  const r1 = await pg.$$eval('#linksTable tbody tr', trs => { const t = trs.find(tr => tr.cells[0].textContent === 'R1'); return t ? [...t.cells].map(c => c.innerText.replace(/\n/g, ' / ')) : null; });
  console.log('[4b] loopactive R1 row:', JSON.stringify(r1));

  // 5: six-hour model, hourly reporting
  await pg.setInputFiles('#fileIn', D + '/split_6h_hourly.inp'); await pg.waitForTimeout(200); await pg.click('#runBtn'); await runDone();
  const ax = await pg.$eval('#chart', s => ({ path: s.querySelector('path').getAttribute('d').slice(0, 60), ticks: [...s.querySelectorAll('text')].filter(t => +t.getAttribute('y') > 280 && /^[\d.]+$/.test(t.textContent)).map(t => [t.textContent, +(+t.getAttribute('x')).toFixed(1)]) }));
  console.log('[5] hourly chart: first path points', ax.path, '| x ticks [label, x] (plot spans x 58..746):', JSON.stringify(ax.ticks));
  const periods = await pg.$eval('#eng-kw', e => e.innerText.match(/Reporting periods\s*([^\n]*)/)[1]);
  console.log('    swmm5-kw reporting periods:', periods);

  // 3: 30-day one-minute model, stop during the swmm5-kw run
  await pg.setInputFiles('#fileIn', D + '/split_30day.inp'); await pg.waitForTimeout(200); await pg.click('#runBtn');
  await pg.waitForFunction(() => { const s = document.querySelector('#eng-kw .prog span'); return s && parseFloat(s.style.width) >= 1; }, null, { timeout: 120000 });
  await pg.click('#stopBtn'); await runDone();
  const v3 = await pg.textContent('#verdict');
  const shown = await pg.$$eval(['#kwCard', '#chartCard', '#splitCard', '#linksCard'].join(','), es => es.filter(e => !e.classList.contains('hidden')).map(e => e.id));
  console.log('[3] stopped verdict:', v3.slice(0, 260)); console.log('    comparison cards still shown:', JSON.stringify(shown));
  
  // 1: in-browser gates incl. the 65-outlet case
  await pg.click('button[data-view="verify"]'); await pg.click('#gateBtn');
  await pg.waitForFunction(() => /networks pass|failed|stopped/.test(document.querySelector('#gateNote').textContent), null, { timeout: 300000 });
  console.log('[1] gates:', await pg.textContent('#gateNote'));
  console.log('    65-outlet row:', (await pg.$$eval('#gateTable tbody tr', trs => trs[trs.length - 1].innerText.replace(/\s+/g, ' '))));
  console.log('errors:', JSON.stringify(errs));
  await b.close();
})();
