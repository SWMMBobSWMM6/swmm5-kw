// The two WebAssembly engines against native builds of the same source and the same libm (musl),
// every mode, byte for byte; then the null effect inside wasm.
//   node tools/wasm_check.js <build-dir> model1.inp ...
// <build-dir> must hold kwswmm-musl and stockseq-musl (tools/build.sh with apt musl-tools).
const fs = require('fs'), os = require('os'), path = require('path'), { execFileSync } = require('child_process');
const R = path.join(__dirname, '..'), B = process.argv[2], models = process.argv.slice(3);
eval(fs.readFileSync(path.join(R, 'wasm/wasi-shim.iife.js'), 'utf8'));
require(path.join(R, 'wasm/kwengine.js'));
const T = fs.mkdtempSync(path.join(os.tmpdir(), 'kwc-'));
function native(exe, f, env) {
  const rpt = path.join(T, 'n.rpt'), out = path.join(T, 'n.out');
  try { fs.unlinkSync(out); } catch (e) {}
  try { execFileSync(path.join(B, exe), [f, rpt, out], { env, stdio: 'ignore' }); } catch (e) {}
  return fs.existsSync(out) ? fs.readFileSync(out) : Buffer.alloc(0);
}
(async () => {
  const KW = new KWEngine(new WebAssembly.Module(fs.readFileSync(path.join(R, 'wasm/swmm524kw.wasm'))));
  const ST = new KWEngine(new WebAssembly.Module(fs.readFileSync(path.join(R, 'wasm/swmm524.wasm'))));
  let same = 0, n = 0, nul = 0, nn = 0, ss = 0, sn = 0;
  for (const f of models) {
    const inp = fs.readFileSync(f, 'utf8'), outs = {};
    for (const [s, l] of [[0, 0], [1, 1], [2, 1], [3, 1]]) {
      const r = await KW.run(inp, { split: s, loop: l }); outs[s + '' + l] = Buffer.from(r.out);
      n++;
      if (Buffer.compare(outs[s + '' + l], native('kwswmm-musl', f, { KWSPLIT: String(s), KWLOOP: String(l) })) === 0) same++;
      else console.log('KW WASM != MUSL', path.basename(f), s, l);
    }
    const st = Buffer.from((await ST.run(inp, {})).out); sn++;
    if (Buffer.compare(st, native('stockseq-musl', f, {})) === 0) ss++; else console.log('STOCK WASM != MUSL', path.basename(f));
    nn++; if (Buffer.compare(outs['00'], outs['11']) === 0) nul++;
  }
  console.log(`swmm524kw.wasm vs native musl: ${same}/${n} byte-identical`);
  console.log(`swmm524.wasm (stock) vs native musl: ${ss}/${sn} byte-identical`);
  console.log(`modes off vs on identical in ${nul}/${nn} models (expect exactly the models with nothing to split or loop)`);
  fs.rmSync(T, { recursive: true, force: true });
  process.exitCode = (same === n && ss === sn) ? 0 : 1;
})();
