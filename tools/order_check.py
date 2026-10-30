# Order independence: shuffle [JUNCTIONS] and [CONDUITS] (3 seeds); link peaks and continuity must not change.
#   python3 tools/order_check.py <build-dir>/kwswmm model1.inp ...
import random, subprocess, re, sys, os, tempfile
TD=tempfile.mkdtemp(); PI=os.path.join(TD,'p.inp'); PR=os.path.join(TD,'p.rpt'); PO=os.path.join(TD,'p.out')
bad=0
def sections(txt):
    out=[]; cur=None
    for line in txt.splitlines():
        if line.startswith('['): cur=line.strip(); out.append([cur,[]])
        elif out: out[-1][1].append(line)
    return out
def permute(txt, seed):
    rnd=random.Random(seed); secs=sections(txt); res=[]
    for name,lines in secs:
        if name in ('[CONDUITS]','[JUNCTIONS]'):
            head=[l for l in lines if l.startswith(';;')]; body=[l for l in lines if l.strip() and not l.startswith(';;')]
            rnd.shuffle(body); lines=head+body+['']
        res.append(name); res.extend(lines)
    return '\n'.join(res)+'\n'
def summary(rpt):
    t=open(rpt,encoding='latin1').read()
    links={}; m=t.find('Link Flow Summary')
    for line in t[m:].splitlines()[8:]:
        p=line.split()
        if len(p)>=3 and p[1] in ('CONDUIT',): links[p[0]]=p[2]
        elif not line.strip() and links: break
    ce=re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',t)
    return links, ce
for model in sys.argv[2:]:
    base=open(model).read(); ref=None; same=0
    for seed in range(4):
        txt=base if seed==0 else permute(base,seed)
        open(PI,'w').write(txt)
        subprocess.run([sys.argv[1],PI,PR,PO],env={'KWSPLIT':'1','KWLOOP':'1'},capture_output=True)
        s=summary(PR)
        if ref is None: ref=s
        else: same += (s==ref)
        if s!=ref: print('  seed',seed,'differs:',s,'vs',ref); bad+=1
    print(model,'renumberings identical to original:',same,'of 3')
sys.exit(1 if bad else 0)
