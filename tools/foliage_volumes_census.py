"""Перепись правила №587 (psp_export.col_foliage_volumes) по выгрузкам SHR_PHANTOM_VOL_INPUTS (tools/psp_export.py N с этим окружением, SHR_FOL_VOL_OLD=1),
файлы build/_rep/exp/lN_inputs.npz. Печатает по уровням, сколько твёрдых объёмов стало мягкими и какие объекты диска."""
import sys, re, collections
sys.path.insert(0,'tools')
import numpy as np
import psp_export as ex
res={}
for L in [1,2,3,4,7]:
    d=np.load(f'build/_rep/exp/l{L}_inputs.npz',allow_pickle=True)
    BX0=d['BX'].copy(); CY0=d['CY'].copy()
    BX,CY,rep=ex.col_foliage_volumes(d['BX'],d['CY'],d['vis'],d['vfl'],d['vtx'],set(d['ufol'].tolist()),list(d['bn']),list(d['cn']))
    sb=int((BX0[:,15]==1).sum()); sc=int((CY0[:,9]==1).sum())
    ents=collections.Counter()
    seen=set()
    for k,i,*_ in rep:
        nm=(d['bn'] if k=='box' else d['cn'])[i]; seen.add(nm)
    for nm in seen: ents[re.sub(r'\d+','#',nm.split('/',1)[-1])]+=1
    print(f"L{L}: твёрдых объёмов {int((BX0[:,15]==0).sum())} ящиков + {int((CY0[:,9]==0).sum())} капсул; уже мягких (eShrub) {sb}+{sc}; стало мягкими ещё {len(rep)} объёмов ({len(seen)} объектов диска)")
    print('   объекты:',dict(ents.most_common(14)))
    if L==1:
        gens51=[(k,i) for k,i,*_ in rep if 'gens51' in (d['bn'] if k=='box' else d['cn'])[i]]
        print('   gens51 (Роб J9-4):',gens51)
