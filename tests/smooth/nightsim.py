import numpy as np, json, sys, glob, os
R='/Users/USER/Downloads/shar-psp-night-w/build/night-final/2026-10-11/'
BASE={1:11.2,2:14.8,3:17.5,4:14.88,5:13.6,6:14.88,7:17.3}; CORR={1:.75,3:.7,7:.9}
# kt scale curves (mean kt cell-model by dd) from cellwaste: now / hybrid, relative to dd=250
DD=np.array([250,200,180,150,115.]); NOW=np.array([33.8,29.3,27.2,23.8,19.4])/33.8; HYB=np.array([24.5,21.6,20.2,17.8,14.6])/33.8
def scale(dd,curve): return np.interp(dd,DD[::-1],curve[::-1])
def load_city(lv):
    P=[];
    for l in open(R+f'city_L{lv}.tsv'):
        if l.startswith('#'): continue
        x,z,km,kw,c=l.split(); P.append((float(x),float(z),float(km)))
    return np.array(P)
levels=[int(a) for a in sys.argv[1:]] or [2,3,5,6]
meta={}
for l in open(R+'results.ndjson'):
    d=json.loads(l)
    if d.get('kind')=='mission': meta[(int(d['level']),int(d['mission']),int(d['seed']))]=d.get('mid')
out=[]
for lv in levels:
    C=load_city(lv)
    for tr in sorted(glob.glob(R+f'missions/L{lv}_m*_s*/trace.tsv')):
        mm=os.path.basename(os.path.dirname(tr)); _,m,s=mm.split('_'); m=int(m[1:]); s=int(s[1:])
        rows=[l.split('\t') for l in open(tr) if not l.startswith('#') and l.strip()]
        if not rows: continue
        a=np.array([[float(v) for v in r] for r in rows])
        x,z=a[:,1],a[:,3]; ai=a[:,6]; trc=a[:,11]; destr=a[:,17]
        # nearest city cell
        idx=[int(np.argmin((C[:,0]-xx)**2+(C[:,1]-zz)**2)) for xx,zz in zip(x,z)]
        kt=C[idx,2]*CORR.get(lv,1.0)
        other=BASE[lv]+2.3*ai+.33*trc+3.2*(destr>0)
        cpu0=other+.32*kt
        # controllers: hybrid only (dd=250); hybrid + adaptive
        cpuH=other+.32*kt*scale(250,HYB)
        dd=250.; ddAvg=cpuH[0]; ddlist=[]; cpuA=[]
        for t in range(len(kt)):
            # city kt at current dd (hybrid)
            cur=other[t]+.32*kt[t]*scale(dd,HYB); cpuA.append(cur); ddAvg+=(cur-ddAvg)*.5
            if ddAvg>31.2+.3: dd=max(150.,dd-12.)
            elif ddAvg<31.2-2.5: dd=min(250.,dd+6.)
            ddlist.append(dd)
        def st(c):
            c=np.array(c); over=c>31; best=run=0
            for o in over:
                run=run+1 if o else 0; best=max(best,run)
            return c.max(),c.mean(),int(over.sum()),best
        out.append((lv,m,s,meta.get((lv,m,s)),len(kt),st(cpu0),st(cpuH),st(cpuA),min(ddlist)))
import collections
agg=collections.defaultdict(list)
for o in out: agg[(o[0],o[3])].append(o)
print('level mission | now max/mean/s>31/run | hybrid | hybrid+adaptive (min dd)')
for (lv,mid),L in sorted(agg.items(), key=lambda kv:-max(o[5][0] for o in kv[1]))[:14]:
    f=lambda i:(np.mean([o[i][0] for o in L]),np.mean([o[i][1] for o in L]),np.mean([o[i][2] for o in L]),np.mean([o[i][3] for o in L]))
    print(f'L{lv} {mid}: now {f(5)[0]:.1f}/{f(5)[1]:.1f}/{f(5)[2]:.0f}/{f(5)[3]:.0f} | hyb {f(6)[0]:.1f}/{f(6)[1]:.1f}/{f(6)[2]:.0f}/{f(6)[3]:.0f} | hyb+adapt {f(7)[0]:.1f}/{f(7)[1]:.1f}/{f(7)[2]:.0f}/{f(7)[3]:.0f} (dd min {np.mean([o[8] for o in L]):.0f})')
tot=[ (np.mean([o[5][2] for o in out]),np.mean([o[6][2] for o in out]),np.mean([o[7][2] for o in out])) ]
print('mean seconds>31 per run (all levels given):',[round(v,1) for v in tot[0]], 'runs',len(out))
