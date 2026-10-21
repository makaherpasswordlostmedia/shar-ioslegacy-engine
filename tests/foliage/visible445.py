#!/usr/bin/env python3
"""#445: actual exporter OLD must turn leaf artwork into HARD ground.
Also retain opaque and alpha grass supports, water exclusion and authored COL.
"""
import os,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import psp_export as E
# Same geometry/material transparency; physical ownership alone separates a
# leaf crown from real alpha-tested grass. A texture-name test cannot pass.
P=np.array([[[.2,1.2,.2],[.2,1.2,1.2],[1.2,1.2,.2]]]*4,float)
flags=np.array([1,1,0,2]);fol=np.array([True,False,False,False])
original=np.array([[[0,0,0],[0,0,3],[3,0,0],[0,1,0]]],float)
hm=np.zeros((4,4,1),dtype=np.int16)
tr,n=E.col_visible_ground(original,P.reshape(-1,3),flags,np.zeros(3),4,4,hm,foliage=fol)
assert np.array_equal(tr[:1],original),'authored ground changed'
assert n==2,f'leaf crown became HARD support: expected two real surfaces, got {n}'
print('PASS: leaf crown excluded; alpha grass/opaque ground retained; water excluded; authored COL unchanged')
