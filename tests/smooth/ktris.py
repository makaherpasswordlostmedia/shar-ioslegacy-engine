import struct, numpy as np, sys, math
LV=int(sys.argv[1]) if len(sys.argv)>1 else 2
P='/Users/USER/Downloads/shar-psp-sonnet-runs-w/build/final-20261010-2056/'+('level.shr' if LV==1 else f'l{LV}/level.shr')
b=open(P,'rb').read(); npc=struct.unpack_from('<I',b,8)[0]; ptab=struct.unpack_from('<I',b,76)[0]; pvsOff=struct.unpack_from('<I',b,88)[0]
dt=np.dtype([('bb','<f4',6),('tex','<i4'),('flags','<i4'),('nv','<i4'),('ni','<i4'),('owner','<i4'),('o','<f4',3),('sc','<f4'),('off','<u4'),('nf','<u4'),('cell','<u4'),('pad','<u4',2)])
pc=np.frombuffer(b,dt,npc,ptab); bb=pc['bb']; tris=pc['ni']//3
ox,oz,pcell=struct.unpack_from('<3f',b,pvsOff+4); W,H,pool,rng=struct.unpack_from('<4I',b,pvsOff+16)
ent=np.frombuffer(b,'<u4',W*H*2,pvsOff+32).reshape(-1,2); poolarr=np.frombuffer(b,'<u2',pool,pvsOff+32+W*H*8)
def planes(fx,fy,fz):
    rx,rz=-fz,fx; rl=math.hypot(rx,rz) or 1; rx/=rl; rz/=rl
    ux,uy,uz=-rz*fy, rz*fx-rx*fz, rx*fy
    tv=math.tan(math.radians(62)*.5)*1.03; th=tv*16/9
    return np.array([[fx*th-rx,fy*th,fz*th-rz],[fx*th+rx,fy*th,fz*th+rz],[fx*tv-ux,fy*tv-uy,fz*tv-uz],[fx*tv+ux,fy*tv+uy,fz*tv+uz]])
DD=[250,220,200,180,150,115]
rows=[]
for line in open(f'/Users/USER/Downloads/shar-psp-night-w/build/night-final/2026-10-11/city_L{LV}.tsv'):
    if line.startswith('#'): continue
    x,z,km,kw,calls=line.split(); x=float(x); z=float(z)
    gx=int((x-ox)//pcell); gz=int((z-oz)//pcell)
    if gx<0 or gz<0 or gx>=W or gz>=H: continue
    e=ent[gz*W+gx]
    if e[1]==0xFFFFFFFF: continue
    lst=poolarr[e[0]:e[0]+e[1]].astype(int); B=bb[lst]; T=tris[lst]
    ey=float((B[:,1].min()+B[:,4].max())/2) if False else 4.0
    dx=np.maximum(np.maximum(B[:,0]-x,x-B[:,3]),0); dy=np.maximum(np.maximum(B[:,1]-ey,ey-B[:,4]),0); dz=np.maximum(np.maximum(B[:,2]-z,z-B[:,5]),0)
    d2=dx*dx+dy*dy+dz*dz
    res=np.zeros((4,len(DD)))
    for h,ang in enumerate((0,90,180,270)):
        f=(math.cos(math.radians(ang)),0.0,math.sin(math.radians(ang))); pl=planes(*f)
        vis=np.ones(len(lst),bool)
        for i in range(4):
            px=np.where(pl[i,0]>0,B[:,3],B[:,0])-x; py=np.where(pl[i,1]>0,B[:,4],B[:,1])-ey; pz=np.where(pl[i,2]>0,B[:,5],B[:,2])-z
            vis&=(px*pl[i,0]+py*pl[i,1]+pz*pl[i,2]>=0)
        for j,d in enumerate(DD):
            ok=vis&(d2<=d*d)&((d2<=rng*rng) if d>rng else True)
            res[h,j]=T[ok].sum()/1000
    rows.append((x,z,float(km),float(kw),res))
R=np.array([[r[4][:,j].mean() for j in range(len(DD))] for r in rows]); Wst=np.array([[r[4][:,j].max() for j in range(len(DD))] for r in rows])
km=np.array([r[2] for r in rows]); kw=np.array([r[3] for r in rows])
print(f'L{LV}: {len(rows)} poses; night mean/worst avg {km.mean():.1f}/{kw.mean():.1f} vs mine (250 m) mean/worst avg {R[:,0].mean():.1f}/{Wst[:,0].mean():.1f}; corr(mean) {np.corrcoef(km,R[:,0])[0,1]:.3f}')
print('drawDist:',DD); print('mean kt (4 headings):',R.mean(0).round(1).tolist()); print('90th pct worst heading:',np.percentile(Wst,90,axis=0).round(1).tolist()); print('max worst:',Wst.max(0).round(1).tolist())
for thr in (40,50,60):
    print(f'poses with worst-heading kt > {thr}:',[int((Wst[:,j]>thr).sum()) for j in range(len(DD))])
