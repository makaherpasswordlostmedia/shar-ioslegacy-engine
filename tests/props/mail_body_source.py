#!/usr/bin/env python3
"""Mailbox authored tensor independently matches its rotated OBB; wrong ATC/box red"""
import copy,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from prop_body_source import body
path=ROOT/'hit-and-run-web/source/game/art/l1z1.p3d'
b=body(path,'l1_mailboxsimpson_Shape')
def judge(b):
 try:
  assert b['atc']==12 and b['attribute']['particle']=='eMail' and b['attribute']['mass']==125
  box,=b['collision_reflected_Z'];assert box['kind']=='box'
  A=np.array(box['axes'])*[1,1,-1];h=np.array(box['halfExtents']);volume=np.prod(h)*8
  c=np.array(box['center'])*[1,1,-1]
  assert np.max(abs(c-b['center_native']))<1e-7
  assert abs(volume-b['volume'])<1e-6
  # Integral of a uniform authored OBB around its centroid, per unit density
  diag=volume*(sum(h*h)-h*h)/3;I=A.T@np.diag(diag)@A
  six=I[[0,0,0,1,1,2],[0,1,2,1,2,2]]
  assert np.max(abs(six-b['inertia_volume_native']))<1e-6 # stored source f32 rounding
  assert np.linalg.eigvalsh(I).min()>0
  assert np.max(abs(six*125/volume-b['inertia_density_scaled_native']))<.0003 # f32 source density rounding only
  return True
 except AssertionError:return False
assert judge(b);print('PASS native rigid OBB/volume/COM/tensor, ATC12 mass125')
bad=copy.deepcopy(b);bad['attribute']['mass']=100;assert not judge(bad);print('RED wrong ATC mailbox mass100')
bad=copy.deepcopy(b);bad['inertia_volume_native']=[sum(b['volume']*x*x/3 for x in [.691,.458]),0,0,sum(b['volume']*x*x/3 for x in [.423,.458]),0,sum(b['volume']*x*x/3 for x in [.423,.691])]
assert not judge(bad);print('RED axis-aligned mesh bbox tensor')
out=ROOT/'build/codex4-mail-source';out.mkdir(exist_ok=True);(out/'source-body.json').write_text(json.dumps(b,indent=2)+'\n')
print('Source geometry only; mailbox flight gate remains FAIL, contact/braking V138')
