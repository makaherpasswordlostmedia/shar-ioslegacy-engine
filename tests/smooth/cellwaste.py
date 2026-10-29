import sys, struct, numpy as np
sys.path.insert(0,'/Users/USER/Downloads/shar-psp-night-w/tools'); import budget as B
LV=int(sys.argv[1]); draw=float(sys.argv[2]) if len(sys.argv)>2 else 250.
path='/Users/USER/Downloads/shar-psp-sonnet-runs-w/build/final-20261010-2056/'+('level.shr' if LV==1 else f'l{LV}/level.shr')
L=B.load(path); recs=L['recs']
own=np.array([r['owner'] for r in recs]); bb=np.array([r['bb'] for r in recs]); c=(bb[:,:3]+bb[:,3:])/2
rad=.5*np.linalg.norm(bb[:,3:]-bb[:,:3],axis=1); ni=np.array([r['ni'] for r in recs])//3; fl=np.array([r['flags'] for r in recs])
d=open(path,'rb').read(); off=struct.unpack_from('<I',d,88)[0]
ox,oz,cell=struct.unpack_from('<3f',d,off+4); W,H,pool,pad=struct.unpack_from('<4I',d,off+16)
ent=np.frombuffer(d,'<u4',2*W*H,off+32).reshape(-1,2); pl=np.frombuffer(d,'<u2',pool,off+32+8*W*H)
cellid=np.array([r['cell'] for r in recs]); opaque=(fl&2)==0; city=(own==0)
ncell=int(cellid[city].max())+1
# cell quadrant groups: by piece centre relative to cell centre
cb=np.zeros((ncell,6)); 
for k in range(len(recs)):
    if city[k]: pass
cc=np.zeros((ncell,3)); cn=np.zeros(ncell)
np.add.at(cc,cellid[city],c[city]); np.add.at(cn,cellid[city],1); cc/=np.maximum(cn,1)[:,None]
grp=((c[:,0]>cc[cellid.clip(0,ncell-1),0]).astype(int)*2+(c[:,2]>cc[cellid.clip(0,ncell-1),2]).astype(int))
cell_tris=np.bincount(cellid[city&opaque],weights=ni[city&opaque],minlength=ncell)
gkey=cellid*4+grp; gtris=np.bincount(gkey[city&opaque],weights=ni[city&opaque],minlength=ncell*4)
hm=L['hm']; rows=[]
for gz in range(H):
    for gx in range(W):
        s,n=ent[gz*W+gx]
        if n==0xFFFFFFFF or n==0: continue
        lst=pl[s:s+n]; x=ox+(gx+.5)*cell; z=oz+(gz+.5)*cell
        hx=int((x-L['hox'])//L['cell']); hz=int((z-L['hoz'])//L['cell'])
        if not (0<=hx<L['W'] and 0<=hz<L['H']): continue
        hs=hm[hz,hx]; hs=hs[hs!=-32768]
        if not len(hs): continue
        y=hs.min()*.01; m=np.zeros(len(recs),bool); m[lst]=True; r=[]
        for h in np.arange(0,2*np.pi,np.pi/2):
            e=np.array([x-np.sin(h)*7.5,y+3.2,z-np.cos(h)*7.5]); f=np.array([x,y+1.4,z])-e; f/=np.linalg.norm(f)
            dv=c-e; dist=np.linalg.norm(dv,axis=1); fw=dv@f; side=np.sqrt(np.maximum(0,dist**2-fw**2))
            inf=(dist-rad<=draw)&~(side*.60-fw*.80>rad)&city&m
            tr=ni[inf&~opaque].sum()
            A=ni[inf&opaque].sum()+tr
            cells=np.unique(cellid[inf&opaque]); Bc=cell_tris[cells].sum()+tr
            gs=np.unique(gkey[inf&opaque]); G=gtris[gs].sum()+tr
            # not in PVS but in called cells (leak) and out-of-frustum
            # гибрид: клетка листом (tris_cell*c + 5.5 мкс) или нужными кусками (tris*c + 17 мкс на кусок), c = 0,32 мкс на треугольник
            need=inf&opaque; ids=np.where(need)[0]; cst=0.0; tr_h=tr; calls_h=0
            for ci in np.unique(cellid[ids]):
                sel=ids[cellid[ids]==ci]; tp=ni[sel].sum(); cl_cost=cell_tris[ci]*0.32+5.5; pc_cost=tp*0.32+17.0*len(sel)
                if cl_cost<=pc_cost: tr_h+=cell_tris[ci]; calls_h+=1
                else: tr_h+=tp; calls_h+=len(sel)
            r.append((A,Bc,G,len(cells),len(gs),inf.sum(),tr_h,calls_h))
        r=np.array(r,float); rows.append((x,z,r[:,0].mean()/1e3,r[:,1].mean()/1e3,r[:,2].mean()/1e3,r[:,0].max()/1e3,r[:,1].max()/1e3,r[:,2].max()/1e3,r[:,3].mean(),r[:,4].mean(),r[:,6].mean()/1e3,r[:,6].max()/1e3,r[:,7].mean()))
R=np.array([[v for v in row[2:]] for row in rows])
print(f'L{LV} draw {draw:.0f} m, {len(rows)} poses: tris kt mean: per-piece {R[:,0].mean():.1f}  whole-cell lists (now) {R[:,1].mean():.1f}  4-group sublists {R[:,2].mean():.1f}')
print(f'   worst-heading kt: per-piece mean {R[:,3].mean():.1f}  cell {R[:,4].mean():.1f}  group {R[:,5].mean():.1f} | 90th pct cell {np.percentile(R[:,4],90):.1f}  group {np.percentile(R[:,5],90):.1f} | max cell {R[:,4].max():.1f} group {R[:,5].max():.1f}')
print(f'   calls/frame mean: cell lists {R[:,6].mean():.0f}, group lists {R[:,7].mean():.0f}; waste of cell lists over per-piece: {(R[:,1].mean()-R[:,0].mean()):.1f} kt ({100*(R[:,1].mean()-R[:,0].mean())/R[:,1].mean():.0f} %)')

print(f'   HYBRID (list or pieces per cell, c=0.32us/tri, 17us/piece): kt mean {R[:,8].mean():.1f}, worst-heading mean {R[:,9].mean():.1f}, 90th pct {np.percentile(R[:,9],90):.1f}, max {R[:,9].max():.1f}; calls/frame {R[:,10].mean():.0f}')
cur=R[:,1]*320+R[:,6]*0; hyb=R[:,8]*320+(R[:,10]-R[:,6])*5.5
print(f'   model cost city (us): now {np.mean(R[:,1]*320+R[:,6]*5.5):.0f}, hybrid {np.mean(R[:,8]*320+R[:,10]*0+0):.0f}+calls; saving est ms {np.mean((R[:,1]-R[:,8])*0.32 - (R[:,10]-R[:,6])*0.0115):.2f}')
