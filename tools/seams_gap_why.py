"""Правка 507: чем вызвана каждая щель кадра GE-модели (tools/seams_ge.py): соседи щели — один кусок / одна клетка / разные клетки, касаются ли
их рёбра (общих вершин, расстояние рёбер). python tools/seams_gap_why.py LEVEL.shr [cat|sep]"""
import sys, numpy as np, collections, struct
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parent)); import seams_ge as G, seams_raster as SR
path=sys.argv[1]; ge=sys.argv[2]
L=G.lib(); pieces=G.load(path); V=G.views(SR.load(path),12)
b=open(path,'rb').read(); ptab,=struct.unpack_from('<I',b,76)
cellof={p['i']:struct.unpack_from('<6fiIIII3ffIII2I',b,ptab+80*p['i'])[17] for p in pieces}
def seg_dist(p0,p1,q0,q1):
    # min distance between two segments (sampled)
    t=np.linspace(0,1,21)[:,None]; A=p0+(p1-p0)*t; B=q0+(q1-q0)*t
    return np.linalg.norm(A[:,None]-B[None],axis=2).min()
out=collections.Counter(); samples=[]
for name,eye,at in V:
    ref=G.frame(L,pieces,eye,at,'ref',True,False); eng=G.frame(L,pieces,eye,at,ge,False,True,True)
    S=G.seams_of(ref,eng); eid,own,Wd=eng[0],eng[4],eng[2]; H,W=S.shape
    for y,x in zip(*np.nonzero(S)):
        res=None
        for dy,dx in ((0,1),(1,0)):
            a=c=None
            for k in range(1,4):
                if a is None and 0<=x-dx*k<W and 0<=y-dy*k<H and eid[y-dy*k,x-dx*k]>=0 and not S[y-dy*k,x-dx*k]: a=eid[y-dy*k,x-dx*k]
                if c is None and 0<=x+dx*k<W and 0<=y+dy*k<H and eid[y+dy*k,x+dx*k]>=0 and not S[y+dy*k,x+dx*k]: c=eid[y+dy*k,x+dx*k]
            if a is not None and c is not None: res=(a,c); break
        if res is None or res[0]==res[1]: continue
        a,c=res; same_cell=cellof[own[a]]==cellof[own[c]]
        TA,TB=Wd[a],Wd[c]
        # min over edge pairs, and number of coincident vertices (<0.1 mm)
        dmin=min(seg_dist(TA[i],TA[(i+1)%3],TB[j],TB[(j+1)%3]) for i in range(3) for j in range(3))
        shared=sum(1 for i in range(3) for j in range(3) if np.linalg.norm(TA[i]-TB[j])<1e-4)
        key=('same-cell' if same_cell else 'diff-cell' )+' '+('sharing %d vertices'%shared)+(' edgedist<1mm' if dmin<1e-3 else ' edgedist<1cm' if dmin<1e-2 else ' edgedist>=1cm')
        out[key]+=1
        if len(samples)<4 and same_cell: samples.append((name,x,y,TA.round(3).tolist(),TB.round(3).tolist(),dmin))
for k,v in sorted(out.items()): print(v,k)
for s in samples: print(s)
