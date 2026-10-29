#!/usr/bin/env python3
"""Validate the real solver against source profiles and independently saved PS2 RAM."""
import json
import struct
import sys
from pathlib import Path
import numpy as np

def operative(p, mass, yoffset, compression):
    six=np.array(p['inertia_origin_per_mass']);xx,xy,xz,yy,yz,zz=six
    I=np.array([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]])
    centre=np.array(p['rest_com_model'])
    for weight, original, comp in zip(p['wheel_com_weight'],p['wheel_centres'],compression):
        a=np.array(original);b=a+np.array([0.,yoffset+comp,0.])
        I+=weight*((b@b-a@a)*np.eye(3)-np.outer(b,b)+np.outer(a,a))
        centre+=weight*(b-a)
    return mass*(I-(centre@centre*np.eye(3)-np.outer(centre,centre)))

def run(log,profiles,ram):
    profiles=json.loads(Path(profiles).read_text());data=Path(ram).read_bytes();seen=set();coupled=0
    for line in Path(log).read_text().splitlines():
        fields=line.split();name=fields[0];v=np.array(list(map(float,fields[1:])));seen.add(name);p=profiles[name]
        from con2h import parse
        con=parse(Path('hit-and-run-web/source/game/scripts/cars')/(name+'.con'))
        nominal,mass=v[:2];expected_mass=nominal*p['mass_fraction']
        I=operative(p,expected_mass,con.get('SetSuspensionYOffset',0.),v[2:6])
        xx,xy,xz,yy,yz,zz=I[[0,0,0,1,1,2],[0,1,2,1,2,2]]
        assert np.isclose(mass,expected_mass,rtol=2e-6),f'{name}: operative mass mismatch'
        assert np.allclose(v[6:12],[xx,xy,xz,yy,yz,zz],rtol=3e-5,atol=.001),f'{name}: articulated tensor mismatch'
        inv=np.linalg.inv(I);actual=v[12:18]
        assert np.allclose(actual,inv[[0,0,0,1,1,2],[0,1,2,1,2,2]],rtol=4e-5,atol=1e-9),name
        if max(abs(xy),abs(xz),abs(yz))>1e-5:coupled+=1
        for pose in range(4):
            w,x,y,z=v[18+7*pose:22+7*pose]
            R=np.array([[1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)],
                        [2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)],
                        [2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)]])
            want=R@np.linalg.solve(I,R.T@np.array([7.,-3.,11.]))
            got=v[22+7*pose:25+7*pose]
            assert np.allclose(got,want,rtol=4e-5,atol=1e-8),f'{name}: world torque pose {pose}'
        if name=='famil_v':
            physical_mass,=struct.unpack_from('<f',data,0x129882c)
            assert abs(mass-physical_mass)<.002,'PS2 operative mass mismatch'
    # At relative frame 60 of the owner's finite original drop, all wheels are
    # unsprung and the operative matrix includes all joints. It is distinct
    # from the raw CHILD tensor stored at 0x1298a5c.
    trace=json.loads(Path(sys.argv[4]).read_text())
    rows=trace if isinstance(trace,list) else trace['rows']
    row=next(x for x in rows if x['rel']==60)
    p=profiles['famil_v'];I=operative(p,1500*p['mass_fraction'],-.23,[0]*4)
    expected=I[[0,0,0,1,1,2],[0,1,2,1,2,2]]*np.array([1,-1,-1,1,1,1])
    original=np.array([row['local'+str(j)] for j in range(13,19)])
    assert np.allclose(expected,original,rtol=3e-6,atol=.003),(expected,original)
    def matrix(v):
        xx,xy,xz,yy,yz,zz=v
        return np.array([[xx,xy,xz],[xy,yy,yz],[xz,yz,zz]])
    for row in rows:
        M=np.array([row['pm'+str(j)] for j in range(16)]).reshape(4,4)[:3,:3]
        body=matrix([row['local'+str(j)] for j in range(13,19)])
        world=matrix([row['local'+str(j)] for j in range(20,26)])
        # 0x12988fc is padding; the inverse starts at 0x1298900.
        inverse=matrix([row['local'+str(j)] for j in range(27,33)])
        # The native logger serializes %.6g, not exact floats. Propagate that
        # rounding interval and single-precision matrix arithmetic explicitly.
        def rounding(a):
            return np.where(a!=0,.5*10.**(np.floor(np.log10(np.maximum(abs(a),1e-30)))-5),0.)
        A=abs(M);B=abs(body);dM=rounding(M);dI=rounding(body)
        bound=rounding(world)+dM.T@B@A+A.T@B@dM+A.T@dI@A+12*np.finfo(np.float32).eps*(A.T@B@A)
        assert (abs(world-M.T@body@M)<=bound).all(),('native world tensor',row['rel'])
        assert np.max(abs(inverse-np.linalg.inv(world)))<4e-8,('native inverse',row['rel'])
    assert seen==set(profiles),'missing car profiles'
    print(f'PASS {len(seen)} source cars × 4 suspension poses, {coupled*4} world torque responses; operative famil_v mass/tensor match original PS2 RAM')

if __name__=='__main__':
    try:
        sys.path.insert(0,'tools');run(*sys.argv[1:4])
    except AssertionError as e:print('FAIL:',e);sys.exit(1)
