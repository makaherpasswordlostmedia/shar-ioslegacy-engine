import struct, numpy as np, sys, collections
LV=int(sys.argv[1]) if len(sys.argv)>1 else 2
P=f'/Users/USER/Downloads/shar-psp-sonnet-runs-w/build/final-20261010-2056/'+('level.shr' if LV==1 else f'l{LV}/level.shr')
b=open(P,'rb').read(); npc=struct.unpack_from('<I',b,8)[0]; ptab=struct.unpack_from('<I',b,76)[0]; pvsOff=struct.unpack_from('<I',b,88)[0]
dt=np.dtype([('bb','<f4',6),('tex','<i4'),('flags','<i4'),('nv','<i4'),('ni','<i4'),('owner','<i4'),('o','<f4',3),('sc','<f4'),('off','<u4'),('nf','<u4'),('cell','<u4'),('pad','<u4',2)])
pc=np.frombuffer(b,dt,npc,ptab)
ox,oz,pcell=struct.unpack_from('<3f',b,pvsOff+4); W,H,pool,rng=struct.unpack_from('<4I',b,pvsOff+16)
ent=np.frombuffer(b,'<u4',W*H*2,pvsOff+32).reshape(-1,2); poolarr=np.frombuffer(b,'<u2',pool,pvsOff+32+W*H*8)
tris=np.where(pc['flags']&16, pc['ni']//3, pc['ni']//3)   # NOIDX: ni = число вершин (треугольники = ni/3), иначе индексы: тоже ni/3
print(f'L{LV}: pieces {npc} PVS grid {W}x{H} cell {pcell} range {rng} pool {pool}')
rows=[]
for line in open(f'/Users/USER/Downloads/shar-psp-night-w/build/night-final/2026-10-11/city_L{LV}.tsv'):
    if line.startswith('#'): continue
    x,z,km,kw,calls=line.split(); rows.append((float(x),float(z),float(km),float(kw),int(calls)))
rows.sort(key=lambda r:-r[3])
c=(pc['bb'][:,:3]+pc['bb'][:,3:])/2
for (x,z,km,kw,calls) in rows[:8]:
    gx=int((x-ox)//pcell); gz=int((z-oz)//pcell); e=ent[gz*W+gx]
    if e[1]==0xFFFFFFFF: continue
    lst=poolarr[e[0]:e[0]+e[1]]; t=tris[lst]; d=np.hypot(c[lst,0]-x,c[lst,2]-z)
    fl=pc['flags'][lst]
    bands=[(0,35),(35,70),(70,115),(115,170),(170,400)]
    bs=' '.join(f'{lo}-{hi}m:{t[(d>=lo)&(d<hi)].sum()/1000:.1f}k' for lo,hi in bands)
    trans=t[(fl&2)>0].sum()/1000; dup=len(lst)-len(set(lst.tolist()))
    big=t.max(); topc=collections.Counter()
    print(f'eye({x:.0f},{z:.0f}) night ktris mean/worst {km:.1f}/{kw:.1f} | PVS list {len(lst)} pieces {t.sum()/1000:.1f}k tris | {bs} | translucent {trans:.1f}k | dup {dup} | biggest piece {big} tris')
