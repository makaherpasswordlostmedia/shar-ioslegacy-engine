#!/usr/bin/env python3
"""Read the owner's disc physics; export the articulated whole-car inertia.

PS2 state_l1_incar corroborates density=SetMass/PhysicsObject.volume,
The dof0 sum is a CHILD aggregate. The operative PS2 matrix combines ALL joints,
transforms each local tensor, adds parallel-axis terms and subtracts the whole
centroid term. Wheel compression changes this matrix every physics step.
Body axes of the port reflect the disc's X; XY and XZ therefore change sign.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'hit-and-run-web/tools')]
import convert
import psp_export
from p3d import read,string
from psp_export import car_physics_object,car_measure,car_info
from car_dump import skeleton
from interiors import leaves

def collision_shapes(root,joints):
    """Authored leaf volumes in the port's body axes, at the closed rest pose.

    Parent volumes are search bounds. Keep joint and owner indices in the
    report: a closed-pose union cannot replace the articulated volumes.
    """
    objects=[c for c in root.children if c.id==0x7010000]
    obj=next((c for c in objects if not string(c.data)[0].lower().endswith('bv')),None)
    if obj is None:raise ValueError('no primary vehicle CollisionObject')
    name=string(obj.data)[0];result=[]
    reflect=np.array([-1.,1.,1.])
    def visit(volume):
        index,owner,count=struct.unpack('<IiI',volume.data)
        children=[c for c in volume.children if c.id==0x7010001]
        if count!=len(children):raise ValueError(f'{name}: invalid child count')
        if children:
            for c in children:visit(c)
            return
        if index>=len(joints):raise ValueError(f'{name}: invalid collision joint {index}')
        item=next(leaves(volume,name));W=joints[index][3]
        # interiors.leaves reflects Z for world export; restore disc local
        # axes before composing the authored joint, then reflect body X.
        restore=lambda v:np.array(v)*[1.,1.,-1.]
        item['center']=((np.r_[restore(item['center']),1.]@W)[:3]*reflect).tolist()
        if item['kind']=='box':
            item['axes']=[(restore(a)@W[:3,:3]*reflect).tolist() for a in item['axes']]
            A=np.array(item['axes']);h=np.array(item['halfExtents'])
            extent=h@abs(A);c=np.array(item['center'])
            item['bounds']=[(c-extent).tolist(),(c+extent).tolist()]
            if not np.allclose(A@A.T,np.eye(3),atol=1e-5,rtol=0):raise ValueError(f'{name}: non-orthonormal collision axes')
        elif item['kind']=='cylinder':
            item['axis']=(restore(item['axis'])@W[:3,:3]*reflect).tolist()
        item.update(joint=index,joint_name=joints[index][0],owner=owner)
        result.append(item)
    for volume in obj.children:
        if volume.id==0x7010001:visit(volume)
    if not result:raise ValueError(f'{name}: no collision leaves')
    return result

def body(path):
    root=read(path);o=car_physics_object(root)
    if o is None:return None
    _,p=string(o.data);_,p=string(o.data,p+4)
    _,volume,_=struct.unpack_from('<Iff',o.data,p)
    comp=next(c for c in root.children if c.id==0x4512)
    _,cp=string(comp.data);skname,_=string(comp.data,cp)
    joints=skeleton(next(c for c in root.children if c.id==0x4500 and string(c.data)[0]==skname))
    rigid_volume=0.;child_tensor=np.zeros(6);origin_tensor=np.zeros((3,3));whole_com=np.zeros(3);whole_joint_volume=0.;wheel_volume=np.zeros(4);wheel_centre=np.zeros((4,3))
    for j in o.children:
        if j.id!=0x7011020:continue
        index,v,_,_,_,dof=struct.unpack_from('<I4fI',j.data)
        vecs=[c for c in j.children if c.id==0x7011002]
        if len(vecs)!=1:raise ValueError(f'{path}: joint without one centre')
        local=np.r_[struct.unpack('<3f',vecs[0].data),1.]
        W=joints[index][3];centre=(local@W)[:3]
        whole_com+=v*centre;whole_joint_volume+=v
        if joints[index][0] in ('w0','w1','w2','w3'):
            pos=joints[index][3][3,:3];slot=(0 if pos[2]>0 else 2)+(1 if pos[0]>0 else 0);wheel_volume[slot]+=v;wheel_centre[slot]+=v*centre
        mats=[c for c in j.children if c.id==0x7011001]
        if len(mats)!=1:raise ValueError(f'{path}: rigid joint without one tensor')
        raw=np.array(struct.unpack('<6f',mats[0].data));xx,xy,xz,yy,yz,zz=raw
        I=np.array([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]]);R=W[:3,:3]
        origin_tensor+=R.T@I@R+v*(np.dot(centre,centre)*np.eye(3)-np.outer(centre,centre))
        if not dof:rigid_volume+=v;child_tensor+=raw
    if not (volume>0 and 0<rigid_volume<=volume*1.001):raise ValueError(f'{path}: invalid volumes')
    if abs(whole_joint_volume/volume-1)>0.005:raise ValueError(f'{path}: joint volumes disagree with the physical object')
    centre=whole_com/whole_joint_volume
    centroid_tensor=origin_tensor-whole_joint_volume*(np.dot(centre,centre)*np.eye(3)-np.outer(centre,centre))
    reflect=np.diag([-1,1,1]);centroid_tensor=reflect@centroid_tensor@reflect;origin_tensor=reflect@origin_tensor@reflect
    six=lambda I:I[[0,0,0,1,1,2],[0,1,2,1,2,2]]
    t=six(centroid_tensor)/whole_joint_volume;xx,xy,xz,yy,yz,zz=t
    eig=np.linalg.eigvalsh([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]])
    if not np.isfinite(t).all() or min(eig)<=0:raise ValueError(f'{path}: invalid tensor')
    centre[0]*=-1
    for i in range(4):
        if wheel_volume[i]>0:wheel_centre[i]/=wheel_volume[i]
    wheel_centre[:,0]*=-1
    measured=car_measure(path);lift=measured['lift'];geom=car_info(path.stem,path)
    shapes=collision_shapes(root,joints)
    # Wheel geometry is authored, not an offset calibrated to the old Family
    # Sedan proxy. The true radius also determines the original spring travel.
    for key in ('wheelX','wheelF','wheelR','wheelRad'):geom[key]=measured[key]
    return {'mass_fraction':whole_joint_volume/volume,'inertia_per_body_mass':t.tolist(),
            'inertia_origin_per_mass':(six(origin_tensor)/whole_joint_volume).tolist(),
            'child_mass_fraction':rigid_volume/volume,'child_inertia_volume':child_tensor.tolist(),
            'rest_com_model':centre.tolist(),'model_lift':lift,
            'wheel_com_weight':(wheel_volume/whole_joint_volume).tolist(),
            'wheel_centres':wheel_centre.tolist(),
            'geometry':[geom[k] for k in ('halfW','halfL','bodyOfs','wheelX','wheelF','wheelR','wheelRad','bodyLo','bodyHi','bandLo','bandHi','step')],
            'whole_volume':volume,'rigid_volume':rigid_volume,'whole_joint_volume':whole_joint_volume,
            'collision_shapes':shapes,
            'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    # car_measure writes psp_carm.json/bin through both modules. Keep these
    # generated files and textures inside this run; concurrent worktrees must
    # never race on the shared asset directory or modify the owner disc tree.
    scratch=a.out.parent/'measure'
    scratch.mkdir(parents=True,exist_ok=True)
    convert.OUT=psp_export.OUT=scratch
    convert.TEX=scratch/'textures'
    convert.TEX.mkdir(exist_ok=True)
    # The owner disc is shared read-only through worktree symlinks. Converter
    # uses its resolved GAME root when writing provenance paths.
    game=(ROOT/'hit-and-run-web/source/game').resolve()
    # The asset checkout can be a symlink into another worktree. Imported
    # converter modules resolve their own __file__ through that symlink, so
    # keep their provenance root aligned with the same resolved asset tree.
    convert.GAME=psp_export.GAME=game
    rows={}
    for con in sorted((game/'scripts/cars').glob('*.con')):
        p=game/'art/cars'/f'{con.stem}.p3d'
        if not p.is_file():continue
        r=body(p)
        if r:rows[con.stem]=r
    def f(x):
        s=f'{x:.9g}';return s+('f' if '.' in s or 'e' in s else '.0f')
    lines=['// Generated by tools/car_inertia_export.py from the owner disc; do not edit',
           '#ifndef CAR_INERTIA_H','#define CAR_INERTIA_H',
           'typedef struct { const char *name; float massFraction, inertia[6], centre[3], lift, geom[12], wheelWeight[4], originInertia[6], wheelCentre[4][3]; } CarBodyPhysics;',
           'static const CarBodyPhysics carBodyPhysics[] = {']
    for name,r in rows.items():lines.append('  {"'+name+'", '+f(r['mass_fraction'])+', {'+', '.join(map(f,r['inertia_per_body_mass']))+'}, {'+', '.join(map(f,r['rest_com_model']))+'}, '+f(r['model_lift'])+', {'+', '.join(map(f,r['geometry']))+'}, {'+', '.join(map(f,r['wheel_com_weight']))+'}, {'+', '.join(map(f,r['inertia_origin_per_mass']))+'}, {'+', '.join('{'+', '.join(map(f,c))+'}' for c in r['wheel_centres'])+'}},')
    lines+=['};','#endif','']
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text('\n'.join(lines))
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(rows,indent=2)+'\n')
    print(f'Exported {len(rows)} native rigid-body physics profiles; all tensors positive definite')

if __name__=='__main__':main()
