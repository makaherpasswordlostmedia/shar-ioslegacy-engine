"""Правка 497: оценка треугольников/кусков/клеток-вызовов в кадре по спискам PVS (было: PVS 115 м + пирамида за ним; стало: PVS 250 м).
python tools/pvs_frame_est.py LEVEL_PVS115.shr LEVEL_PVS250.shr [дальность 250]   (два файла одного уровня: tools/pvs --samples 5 и --range 250)"""
import sys, struct, numpy as np
sys.path.insert(0,'tools'); import budget as B
p115,p250=sys.argv[1],sys.argv[2]; draw=float(sys.argv[3]) if len(sys.argv)>3 else 250.
L=B.load(p115); recs=L['recs']
own=np.array([r['owner'] for r in recs]); bb=np.array([r['bb'] for r in recs]); c=(bb[:,:3]+bb[:,3:])/2
rad=.5*np.linalg.norm(bb[:,3:]-bb[:,:3],axis=1); ni=np.array([r['ni'] for r in recs])//3; fl=np.array([r['flags'] for r in recs])
def pvs(path):
    d=open(path,'rb').read(); off=struct.unpack_from('<I',d,88)[0]
    ox,oz,cell=struct.unpack_from('<3f',d,off+4); W,H,pool,pad=struct.unpack_from('<4I',d,off+16)
    ent=np.frombuffer(d,'<u4',2*W*H,off+32).reshape(-1,2); pl=np.frombuffer(d,'<u2',pool,off+32+8*W*H)
    return dict(ox=ox,oz=oz,cell=cell,W=W,H=H,ent=ent,pool=pl,pad=pad)
P115,P250=pvs(p115),pvs(p250)
print('pads',P115['pad'],P250['pad'])
def lst(P,x,z):
    gx=int((x-P['ox'])//P['cell']); gz=int((z-P['oz'])//P['cell'])
    if not(0<=gx<P['W'] and 0<=gz<P['H']): return None
    s,n=P['ent'][gz*P['W']+gx]
    return None if n==0xFFFFFFFF else P['pool'][s:s+n]
cone=(0.60,0.80); hm=L['hm']; res=[]
cellid=np.array([r['cell'] for r in recs]); opaque=(fl&2)==0
ncell=int(cellid[own==0].max())+1
cell_tris=np.bincount(cellid[(own==0)&opaque],weights=ni[(own==0)&opaque],minlength=ncell)
def dlcost(m):
    cells=np.unique(cellid[m&opaque]); return cell_tris[cells].sum()+ni[m&~opaque].sum(), len(cells)+(m&~opaque).sum()
for gz in range(0,P250['H'],2):
    for gx in range(0,P250['W'],2):
        x=P250['ox']+(gx+.5)*P250['cell']; z=P250['oz']+(gz+.5)*P250['cell']
        l115=lst(P115,x,z); l250=lst(P250,x,z)
        if l115 is None or l250 is None: continue
        # ground y from heightmap
        hx=int((x-L['hox'])//L['cell']); hz=int((z-L['hoz'])//L['cell'])
        if not(0<=hx<L['W'] and 0<=hz<L['H']): continue
        hs=hm[hz,hx]; hs=hs[hs!=-32768]
        if not len(hs): continue
        y=hs.min()*.01
        for h in np.arange(0,2*np.pi,np.pi/2):
            e=np.array([x-np.sin(h)*7.5,y+3.2,z-np.cos(h)*7.5]); f=np.array([x,y+1.4,z])-e; f/=np.linalg.norm(f)
            dv=c-e; dist=np.linalg.norm(dv,axis=1); fw=dv@f; side=np.sqrt(np.maximum(0,dist**2-fw**2))
            inf=(dist-rad<=draw)&~(side*cone[0]-fw*cone[1]>rad)&(own==0)
            # A: now: list115 within 115 + frustum beyond 115 (bbox dist ~ dist-rad)
            near=(dist-rad)<=115.
            m115=np.zeros(len(recs),bool); m115[l115]=True
            A=inf&((near&m115)|(~near))
            m250=np.zeros(len(recs),bool); m250[l250]=True
            Bm=inf&m250
            res.append((ni[A].sum(),A.sum(),ni[Bm].sum(),Bm.sum(),ni[inf].sum(),inf.sum())+dlcost(A)+dlcost(Bm)+dlcost(inf))
r=np.array(res,float); print('frames',len(r))
for name,i in (('frustum only',4),('now (PVS115+frustum)',0),('new (PVS250)',2)):
    print(f'{name:22s} tris p50 {np.median(r[:,i])/1e3:5.1f}k mean {r[:,i].mean()/1e3:5.1f}k p90 {np.percentile(r[:,i],90)/1e3:5.1f}k | pieces p50 {np.median(r[:,i+1]):.0f} mean {r[:,i+1].mean():.0f} p90 {np.percentile(r[:,i+1],90):.0f}')

print('--- display-list model (whole visible cell drawn)')
for name,i in (('frustum only',10),('now (PVS115+frustum)',6),('new (PVS250)',8)):
    print(f'{name:22s} tris p50 {np.median(r[:,i])/1e3:5.1f}k mean {r[:,i].mean()/1e3:5.1f}k p90 {np.percentile(r[:,i],90)/1e3:5.1f}k | calls p50 {np.median(r[:,i+1]):.0f} mean {r[:,i+1].mean():.0f} p90 {np.percentile(r[:,i+1],90):.0f}')
