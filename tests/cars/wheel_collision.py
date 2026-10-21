#!/usr/bin/env python3
"""Compare production tyre spheres with independently read disc geometry and PS2.

Source object: the car's only CompositeDrawable names its skeleton; the primary
CollisionObject carries that same name (case-sensitive). The *BV objects own a
separate skeleton and are not the tyre colliders. Every candidate is recorded.

The source sweep covers rest centres/radii, current suspension, steering of
the front wheels and wheel roll of the authored off-pivot sphere centre.
The native comparison covers the existing L1 famil_v snapshots only; famil_v
spheres sit on their pivots, so it does not exercise steering or roll.

Negative controls, each must FAIL with a measured error:
  --old-proxy      production mesh proxy (CAR_WHEEL_COLLISION_PROXY_OLD)
  --rigid          production ignores steering/roll (CAR_WHEEL_COLLIDER_RIGID_OLD)
  --wrong-object   oracle reads the *BV CollisionObject instead of the primary
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'hit-and-run-web/tools')]
from p3d import read,string
from car_dump import skeleton

SPHERE,CYLINDER,BOX,VECTOR=0x7010002,0x7010003,0x7010004,0x7010007


def source(name,wrong=False):
    path=ROOT/'hit-and-run-web/source/game/art/cars'/f'{name}.p3d'
    root=read(path)
    comps=[c for c in root.children if c.id==0x4512]
    assert len(comps)==1,f'{name}: {len(comps)} CompositeDrawables'
    drawable,offset=string(comps[0].data);skname,_=string(comps[0].data,offset)
    objects=[c for c in root.children if c.id==0x7010000]
    candidates=[string(c.data)[0] for c in objects]
    primary=[c for c in objects if string(c.data)[0]==drawable]
    assert len(primary)==1 and skname==drawable,f'{name}: primary candidates {candidates} for {drawable}/{skname}'
    if wrong:
        others=[c for c in objects if string(c.data)[0]!=drawable]
        if not others:return None
        obj=others[0]
    else:obj=primary[0]
    chosen=string(obj.data)[0]
    skeletons=[c for c in root.children if c.id==0x4500 and string(c.data)[0]==chosen]
    assert len(skeletons)==1,f'{name}: skeleton for {chosen}'
    joints=skeleton(skeletons[0])
    rows=[None]*4;kinds=[]
    def visit(node):
        joint,owner,count=struct.unpack('<IiI',node.data)
        if count:
            for child in node.children:
                if child.id==0x7010001:visit(child)
            return
        if joints[joint][0] not in ('w0','w1','w2','w3'):return
        W=joints[joint][3];pivot=W[3,:3]
        slot=(0 if pivot[2]>0 else 2)+(1 if pivot[0]>0 else 0)
        shape=next(c for c in node.children if c.id in (SPHERE,CYLINDER,BOX))
        kinds.append(hex(shape.id))
        if shape.id!=SPHERE:return
        local=np.array(struct.unpack('<3f',next(c for c in shape.children if c.id==VECTOR).data))
        assert rows[slot] is None,f'{name}: duplicate slot {slot}'
        rows[slot]=dict(joint=joint,pivot=pivot*[-1,1,1],offset=(local@W[:3,:3])*[-1,1,1],
                        radius=struct.unpack('<f',shape.data)[0],rest=W)
    for child in obj.children:
        if child.id==0x7010001:visit(child)
    if not wrong:assert all(row is not None for row in rows),f'{name}: missing tyre sphere'
    return dict(rows=rows,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),drawable=drawable,
                chosen=chosen,candidates=candidates,kinds=kinds)


def rotation(q):
    w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)],
                     [2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)],
                     [2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)]])


def articulation(steer,spin):
    # Roll about the axle (body X), then steer about body Y. Positive steer
    # turns body +Z towards +X, the same direction the tyre force uses.
    a,b=steer,spin
    Ry=np.array([[np.cos(a),0,np.sin(a)],[0,1,0],[-np.sin(a),0,np.cos(a)]])
    Rx=np.array([[1,0,0],[0,np.cos(b),-np.sin(b)],[0,np.sin(b),np.cos(b)]])
    return Ry@Rx


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--old-proxy',action='store_true')
    ap.add_argument('--rigid',action='store_true')
    ap.add_argument('--wrong-object',action='store_true')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    exe=args.out/'wheel_collision'
    command=['cc','-std=c11','-O2','-I',str(ROOT/'viewer')]
    if args.old_proxy:command+=['-DCAR_WHEEL_COLLISION_PROXY_OLD=1']
    if args.rigid:command+=['-DCAR_WHEEL_COLLIDER_RIGID_OLD=1']
    subprocess.run(command+[str(ROOT/'tests/cars/wheel_collision.c'),str(ROOT/'viewer/col.c'),'-lm','-o',str(exe)],check=True)
    text=subprocess.check_output([str(exe.resolve())],text=True)
    (args.out/'source.tsv').write_text(text)
    cache={};failures=[];checks=0;worst=0;uncovered=set();articulated=0
    for line in text.splitlines():
        name,*raw=line.split();v=np.array(list(map(float,raw)))
        if name not in cache:cache[name]=source(name,args.wrong_object)
        item=cache[name]
        if item is None:uncovered.add(name);continue
        R=rotation(v[:4]);position=v[4:7];yoffset,limit=v[7:9];comp=v[9:13];steer=v[13];spin=v[14:18];actual=v[18:].reshape(4,4)
        for i,sphere in enumerate(item['rows']):
            if sphere is None:
                failures.append(dict(name=name,slot=i,reason='chosen object has no tyre sphere on this wheel',kinds=item['kinds']));checks+=1;continue
            A=articulation(steer if i<2 else 0.,spin[i])
            local=sphere['pivot']+A@sphere['offset']+np.array([0,yoffset+np.clip(comp[i],0,limit),0])
            if not np.allclose(A@sphere['offset'],sphere['offset'],atol=1e-6,rtol=0):articulated+=1
            expected=position+R@local
            bound=16*np.finfo(np.float32).eps*(abs(position)+abs(R)@abs(local)+1)
            error=np.linalg.norm(expected-actual[i,:3]);worst=max(worst,float(error));checks+=1
            if not ((abs(expected-actual[i,:3])<=bound).all() and np.isclose(actual[i,3],sphere['radius'],rtol=1e-8,atol=0)):
                failures.append(dict(name=name,slot=i,center_error_m=float(error),radius_error_m=float(actual[i,3]-sphere['radius'])))
    native=[]
    if not args.wrong_object:
        fam=cache['famil_v']['rows']
        famil_offset=max(float(np.linalg.norm(s['offset'])) for s in fam)
        for state in [ROOT/'build/ps2ref/state_l1_incar.p2s']+[ROOT/f'build/twins/o4/b2_loop/snap_{n}.p2s' for n in [12000,15000,21000]]:
            with zipfile.ZipFile(state) as archive:ram=archive.read('eeMemory.bin')
            u=lambda at:struct.unpack_from('<I',ram,at)[0]
            floats=lambda at,n:np.array(struct.unpack_from('<'+str(n)+'f',ram,at))
            model=floats(0xa21860+16,16).reshape(4,4);inv=np.linalg.inv(model)
            bones=u(u(0xa21860+0xa8))
            comp=[]
            for s in fam:
                current=floats(bones+s['joint']*192+104,16).reshape(4,4)@inv
                comp.append(float(current[3,1]-s['rest'][3,1])+.23)
            # famil_v spheres are on their pivots: steering/roll cannot move them.
            spec='famil_v '+' '.join(map(str,model.ravel().tolist()+comp+[0.]*5))+'\n'
            log=subprocess.check_output([str(exe.resolve()),'--pose'],input=spec,text=True)
            (args.out/(state.stem+'-native.tsv')).write_text(log)
            actual=np.array(list(map(float,log.split()[1:])))[18:].reshape(4,4)
            obj=u(0xa21860+0x74);parent=u(obj+0x20);children=u(parent+0x34);array=u(children+12)
            native_by_joint={u(u(array+4*i)+0x28):u(array+4*i) for i in range(u(children+4))}
            for i,s in enumerate(fam):
                p=native_by_joint[s['joint']];expected=floats(p+8,3)*[1,1,-1];radius=floats(p+0x4c,1)[0]
                error=float(np.linalg.norm(actual[i,:3]-expected))
                bound=16*np.finfo(np.float32).eps*(abs(expected)+1)
                ok=bool((abs(actual[i,:3]-expected)<=bound).all() and np.isclose(actual[i,3],radius,rtol=1e-8,atol=0))
                native.append(dict(state=str(state.relative_to(ROOT)),slot=i,passed=ok,center_error_m=error,sha256=hashlib.sha256(state.read_bytes()).hexdigest()))
    else:famil_offset=None
    covered={k:v for k,v in cache.items() if v is not None}
    report=dict(passed=not failures and all(row['passed'] for row in native),
                old_proxy=args.old_proxy,rigid=args.rigid,wrong_object=args.wrong_object,
                source_cars=len(covered),uncovered_cars=sorted(uncovered),source_checks=checks,articulated_checks=articulated,
                source_failures=len(failures),worst_source_center_error_m=worst,failures=failures[:30],native=native,
                famil_v_max_offset_m=famil_offset,
                selection={k:dict(drawable=v['drawable'],chosen=v['chosen'],candidates=v['candidates'],sha256=v['sha256']) for k,v in covered.items()},
                scope='lateral tyre sphere selection, rest centres/radii, current suspension, front steering and wheel roll of off-pivot centres; '
                      'native PS2 covers famil_v centres only; no contact forces')
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    tag='PASS' if report['passed'] else 'FAIL'
    print(f"{tag} {checks} source spheres ({articulated} moved by steer/roll) over {len(covered)} cars; failures={len(failures)}; "
          f"worst={worst:.6g} m; native={sum(r['passed'] for r in native)}/{len(native)}"+(f"; uncovered={len(uncovered)}" if uncovered else ''))
    return int(not report['passed'])


if __name__=='__main__':
    raise SystemExit(main())
