"""Правка 507: мерцание щелей под джиттером. Для каждого вида считает щели при сдвигах мира (пиксели) и сравнивает множества: объединение/везде.
python tools/seams_flicker.py LEVEL.shr sep|cat "0.25,0.25;-0.25,-0.25;0.25,-0.25;-0.25,0.25"   (эталон считается с тем же сдвигом)"""
import sys, os, numpy as np
sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parent)); import seams_ge as G, seams_raster as SR
path=sys.argv[1]; ge=sys.argv[2]; phases=[tuple(map(float,p.split(','))) for p in sys.argv[3].split(';')]
L=G.lib(); pieces=G.load(path); V=G.views(SR.load(path),12)
tu=ti=t0=0
for name,eye,at in V:
    sets=[]
    for jx,jy in phases:
        os.environ['SEAMS_JIT']=f'{jx},{jy}'
        ref=G.frame(L,pieces,eye,at,'ref',True,False)
        eng=G.frame(L,pieces,eye,at,ge,False,True,True); sets.append(G.seams_of(ref,eng))
    os.environ['SEAMS_JIT']='0,0'
    U=np.logical_or.reduce(sets); I=np.logical_and.reduce(sets); tu+=int(U.sum()); ti+=int(I.sum()); t0+=int(np.mean([s.sum() for s in sets]))
print(f'{ge} phases {sys.argv[3]}: mean gaps per phase {t0}, union {tu}, always-on {ti}, flicker (union-always) {tu-ti}  [{len(V)} views, 1 frame]')
