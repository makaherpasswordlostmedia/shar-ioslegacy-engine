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
import itertools
levels=[2,3,5,6,7]
PARAMS=[(12,150),(30,150),(30,130),(60,130),(30,115),(60,115)]
meta={}
for l in open(R+'results.ndjson'):
    d=json.loads(l)
    if d.get('kind')=='mission': meta[(int(d['level']),int(d['mission']),int(d['seed']))]=d.get('mid')

def run(DOWN,FLOOR,UP=6.):
    out=[]
    for lv in levels:
        C=load_city(lv)
        for tr in sorted(glob.glob(R+f'missions/L{lv}_m*_s*/trace.tsv')):
            mm=os.path.basename(os.path.dirname(tr)); _,m,s_=mm.split('_')
            rows=[l.split('\t') for l in open(tr) if not l.startswith('#') and l.strip()]
            if not rows: continue
            a=np.array([[float(v) for v in r] for r in rows]); x,z=a[:,1],a[:,3]; ai=a[:,6]; trc=a[:,11]; destr=a[:,17]
            idx=[int(np.argmin((C[:,0]-xx)**2+(C[:,1]-zz)**2)) for xx,zz in zip(x,z)]
            kt=C[idx,2]*CORR.get(lv,1.0); other=BASE[lv]+2.3*ai+.33*trc+3.2*(destr>0)
            cpu0=other+.32*kt; dd=250.; ddAvg=other[0]+.32*kt[0]*scale(250,HYB); cpuA=[]
            for t in range(len(kt)):
                cur=other[t]+.32*kt[t]*scale(dd,HYB); cpuA.append(cur); ddAvg+=(cur-ddAvg)*.5
                if ddAvg>31.5: dd=max(FLOOR,dd-DOWN)
                elif ddAvg<28.7: dd=min(250.,dd+UP)
            def st(c):
                c=np.array(c); over=c>31; return c.max(),int(over.sum())
            out.append((st(cpu0),st(other+.32*kt*scale(250,HYB)),st(cpuA)))
    return out
for DOWN,FLOOR in PARAMS:
    o=run(DOWN,FLOOR)
    print(f'down {DOWN} m/s floor {FLOOR}: seconds>31 per run now {np.mean([v[0][1] for v in o]):.1f} -> hybrid {np.mean([v[1][1] for v in o]):.1f} -> hybrid+adaptive {np.mean([v[2][1] for v in o]):.1f}; mean of max ms now {np.mean([v[0][0] for v in o]):.1f} hyb {np.mean([v[1][0] for v in o]):.1f} adapt {np.mean([v[2][0] for v in o]):.1f}; worst run max: {max(v[2][0] for v in o):.1f}')
