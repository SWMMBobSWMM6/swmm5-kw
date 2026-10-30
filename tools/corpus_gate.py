#!/usr/bin/env python3
"""Corpus gate for the KW/SF extension.

  corpus_gate.py BUILD_DIR CORPUS_DIR RESULTS.jsonl [--list FILE] [--exclude FILE]
                 [--routing KINWAVE,STEADY] [--modes 00,11] [--timeout S] [--jobs N]

Every model runs through BUILD_DIR/stockseq (unmodified EPA 5.2.4) and through
BUILD_DIR/kwswmm once per mode setting ("00" = extension off, "11" = HEAD split +
loop iteration, "21" = CAPACITY, "31" = AREA). Both drivers use the same call
sequence (open, start, step, end, report, close), so byte comparison is fair.

For each mode the record says whether the .out is identical byte for byte and the
.rpt identical after dropping the three wall-clock lines. The two contract claims:

  off means stock      mode 00 identical to stock on every model
  on changes nothing   mode 11 identical to stock on every model stock finishes
                       without ERROR 131 or 133

Models that stock stops with ERROR 131 (loop) or ERROR 133 (multi-outlet junction)
are the census: the record keeps what the extended run did (return code, routing
continuity, split junctions, loop links, sweeps).

Resumable: models already in RESULTS are skipped. Same caps as swmm5-rust's gate:
3 GiB address space and 2 GiB per file, wall-clock timeout per run.
"""
import sys, os, re, subprocess, hashlib, json, time, tempfile, argparse, resource
from concurrent.futures import ThreadPoolExecutor, as_completed

ap = argparse.ArgumentParser()
ap.add_argument('build'); ap.add_argument('corpus'); ap.add_argument('results')
ap.add_argument('--list'); ap.add_argument('--exclude')
ap.add_argument('--routing', default='', help='comma list; only models whose FLOW_ROUTING is in it')
ap.add_argument('--modes', default='00,11')
ap.add_argument('--timeout', type=float, default=300)
ap.add_argument('--jobs', type=int, default=2)
ap.add_argument('--mem', type=float, default=3)
ap.add_argument('--force-routing', default='', help='what-if: run a copy of each model with FLOW_ROUTING set to this')
a = ap.parse_args()
B = os.path.abspath(a.build); C = os.path.abspath(a.corpus)
STOCK = os.path.join(B, 'stockseq'); KW = os.path.join(B, 'kwswmm')
MODES = [m for m in a.modes.split(',') if m]
CLOCK = (b'Analysis begun on', b'Analysis ended on', b'Total elapsed time')
TMP = os.environ.get('TMPDIR', '/tmp')

def routing_of(path):
    """FLOW_ROUTING from [OPTIONS]; SWMM's default is KINWAVE."""
    sec = None
    try:
        with open(path, encoding='latin-1') as f:
            for line in f:
                s = line.split(';', 1)[0].strip()
                if not s: continue
                if s.startswith('['): sec = s.upper(); continue
                if sec == '[OPTIONS]':
                    p = s.split()
                    if len(p) >= 2 and p[0].upper() == 'FLOW_ROUTING': return p[1].upper()
    except OSError:
        return '?'
    return 'KINWAVE'

def limits():
    if a.mem > 0:
        n = int(a.mem * (1 << 30)); resource.setrlimit(resource.RLIMIT_AS, (n, n))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 << 30, 2 << 30))

def digest(path, normalize=False):
    if not os.path.exists(path): return hashlib.sha256(b'').hexdigest(), 0, b''
    h = hashlib.sha256(); n = 0; head = b''
    with open(path, 'rb') as f:
        if normalize:
            for line in f:
                n += len(line)
                if any(c in line for c in CLOCK): continue
                h.update(line)
                if len(head) < 400000: head += line
        else:
            while True:
                b = f.read(1 << 20)
                if not b: break
                n += len(b); h.update(b)
    return h.hexdigest(), n, head

STAT = re.compile(rb'rc=(-?\d+) split=(\S+) back=(\S+) allocs=(\S+) maxImb=(\S+) loopSteps=(\S+) '
                  rb'meanSweeps=(\S+) maxSweeps=(\S+) nonConv=(\S+) maxRes=(\S+) headIt=(\S+)')
KEYS = ('rc', 'split', 'back', 'allocs', 'maxImb', 'loopSteps', 'meanSweeps', 'maxSweeps', 'atCap', 'maxRes', 'headIt')

def run(exe, inp, work, env=None):
    rpt = os.path.join(work, 'm.rpt'); out = os.path.join(work, 'm.out')
    t0 = time.perf_counter(); so = b''
    try:
        p = subprocess.run([exe, inp, rpt, out], cwd=os.path.dirname(inp), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=(a.timeout or None), preexec_fn=limits)
        rc = p.returncode; so = p.stdout
    except subprocess.TimeoutExpired:
        rc = 'timeout'
    dt = time.perf_counter() - t0
    r = digest(rpt, True); o = digest(out)
    for fp in (rpt, out):
        try: os.remove(fp)
        except OSError: pass
    st = None
    m = STAT.search(so)
    if m: st = {k: float(v) for k, v in zip(KEYS, m.groups())}
    return rc, dt, r, o, st

def errors(head):
    return sorted(set(int(x) for x in re.findall(rb'ERROR (\d+)', head)))

def continuity(head):
    t = head.decode('latin-1')
    i = t.find('Flow Routing Continuity')
    if i < 0: return None
    m = re.search(r'Continuity Error \(%\) \.+\s+(-?[\d.]+|-?nan|-?inf)', t[i:])
    return m.group(1) if m else None

def kwblock(head):
    t = head.decode('latin-1'); i = t.find('KW/SF extension')
    return t[i:i + 1500] if i >= 0 else ''

def force_copy(inp, method):
    """A copy of inp beside it (so relative file names still resolve) with FLOW_ROUTING = method."""
    lines = open(inp, encoding='latin-1').read().split('\n'); sec = ''; at = -1; done = False
    for i, raw in enumerate(lines):
        s = raw.split(';', 1)[0].strip()
        if not s: continue
        if s.startswith('['): sec = s.upper(); at = i if sec == '[OPTIONS]' else at; continue
        if sec == '[OPTIONS]' and s.split()[0].upper() == 'FLOW_ROUTING': lines[i] = 'FLOW_ROUTING         ' + method; done = True; break
    if not done:
        if at >= 0: lines.insert(at + 1, 'FLOW_ROUTING         ' + method)
        else: lines = ['[OPTIONS]', 'FLOW_ROUTING         ' + method, ''] + lines
    fd, path = tempfile.mkstemp(prefix='.kwwhatif_', suffix='.inp', dir=os.path.dirname(inp)); os.close(fd)
    open(path, 'w', encoding='latin-1').write('\n'.join(lines)); return path

def one(inp):
    if a.force_routing:
        cp = force_copy(inp, a.force_routing.upper())
        try:
            rec = one_run(cp); rec['inp'] = os.path.relpath(inp, C); rec['forced'] = a.force_routing.upper(); rec['routing_in_file'] = routing_of(inp)
            return rec
        finally:
            try: os.remove(cp)
            except OSError: pass
    return one_run(inp)

def one_run(inp):
    rec = dict(inp=os.path.relpath(inp, C), routing=routing_of(inp))
    with tempfile.TemporaryDirectory(dir=TMP) as d:
        rc, dt, r0, o0, _ = run(STOCK, inp, d)
        rec.update(rc_stock=rc, t_stock=round(dt, 4), out_bytes=o0[1], out_sha=o0[0][:16],
                   rpt_bytes=r0[1], stock_errors=errors(r0[2]))
        census = bool(set(rec['stock_errors']) & {131, 133})
        rec['census'] = census
        if rc == 'timeout':                       # EPA itself did not finish: nothing to compare
            rec['inconclusive'] = 'stock run hit the time cap'
            return rec
        for m in MODES:
            env = dict(os.environ, KWSPLIT=m[0], KWLOOP=m[1])
            rc, dt, r, o, st = run(KW, inp, d, env)
            sm = dict(rc=rc, t=round(dt, 4), out_same=(o[0] == o0[0] and o[1] == o0[1]),
                      rpt_same=(r[0] == r0[0]))
            if not sm['rpt_same']:
                l1 = r0[2].split(b'\n'); l2 = r[2].split(b'\n')
                for i, (x, y) in enumerate(zip(l1, l2)):
                    if x != y:
                        sm['rpt_first_diff'] = [i, x.decode('latin-1')[:120], y.decode('latin-1')[:120]]; break
            if m != '00' and (census or not (sm['out_same'] and sm['rpt_same'])):
                sm['errors'] = errors(r[2]); sm['continuity'] = continuity(r[2]); sm['stats'] = st
                sm['kw_block'] = kwblock(r[2])
            rec['m' + m] = sm
    return rec

if a.list:
    models = [os.path.join(C, l.strip()) for l in open(a.list) if l.strip()]
else:
    models = []
    for root, dirs, files in os.walk(C):
        dirs[:] = [x for x in dirs if x != '.git']
        models += [os.path.join(root, f) for f in files if f.lower().endswith('.inp')]
    models.sort()
if a.exclude:
    ex = set(os.path.join(C, l.strip()) for l in open(a.exclude) if l.strip())
    models = [m for m in models if m not in ex]
if a.routing:
    want = set(a.routing.upper().split(','))
    models = [m for m in models if routing_of(m) in want]
done = set()
if os.path.exists(a.results):
    for l in open(a.results):
        try: done.add(json.loads(l)['inp'])
        except Exception: pass
todo = [m for m in models if os.path.relpath(m, C) not in done]
print(f'{len(models)} models, {len(done)} already done, {len(todo)} to run, modes {MODES}', flush=True)
with open(a.results, 'a') as fo, ThreadPoolExecutor(a.jobs) as px:
    futs = {px.submit(one, m): m for m in todo}
    n = 0
    for fu in as_completed(futs):
        rec = fu.result(); fo.write(json.dumps(rec) + '\n'); fo.flush(); n += 1
        for m in MODES:
            sm = rec.get('m' + m)
            if sm is None: print('INCONCLUSIVE', rec['inp'], flush=True); break
            if not (sm['out_same'] and sm['rpt_same']) and not (m != '00' and rec['census']):
                print('DIFF', m, rec['inp'], sm.get('rpt_first_diff'), flush=True)
        if n % 100 == 0: print(f'{n}/{len(todo)}', flush=True)
print('done', flush=True)
