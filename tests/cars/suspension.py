#!/usr/bin/env python3
"""Compare real C contacts with an independent bounded active-set solution."""
import itertools,json,sys
from pathlib import Path
import numpy as np
profiles=json.loads(Path(sys.argv[2]).read_text());sys.path.insert(0,'tools')
from con2h import parse
from native_inertia import operative
count=0
for line in Path(sys.argv[1]).read_text().splitlines():
    name,*raw=line.split();p=profiles[name];v=np.array(list(map(float,raw)));dt=v[0];w,x,y,z=v[1:5];q=v[5:].reshape(4,9)
    con=parse(Path('hit-and-run-web/source/game/scripts/cars')/(name+'.con'));mass=con['SetMass']*p['mass_fraction']
    # Правка 354 (как viewer/car.c nativeBodyFill): радиус колеса подвески — высота центра колеса модели над землёй в покое
    # (сфера w0..w3 + model_lift), если у четырёх колёс она одна (±1 см); иначе — радиус меша (geometry[6])
    h=[s['center'][1]+p['model_lift'] for s in p['collision_shapes'] if s['kind']=='sphere' and s['joint_name'] in ('w0','w1','w2','w3')]
    radius=sum(h)/4 if len(h)==4 and max(h)-min(h)<=.01 and min(h)>.05 else p['geometry'][6]
    lim=max(.03,radius*con['SetSuspensionLimit']);kb=con['SetSpringK']*mass*16/lim
    eq=min(((1+20*(mass*16*.25)/kb)**.5-1)/10,lim*.9)
    I=operative(p,mass,con.get('SetSuspensionYOffset',0.),[eq]*4)
    R=np.array([[1-2*(y*y+z*z),2*(x*y-w*z),2*(x*z+w*y)], [2*(x*y+w*z),1-2*(x*x+z*z),2*(y*z-w*x)], [2*(x*z-w*y),2*(y*z+w*x),1-2*(x*x+y*y)]])
    r,n,D,free,actual=q[:,:3],q[:,3:6],q[:,6],q[:,7],q[:,8];J=np.cross(r,n)
    W=n@n.T/mass+J@R@np.linalg.inv(I)@R.T@J.T
    # Symmetric positive-definite form of backward Euler: (1/D+dt*W)f=-v.
    A=np.diag(1/D)+dt*W;b=-free;cap=6*mass*16;expected=None
    for states in itertools.product((0,1,2),repeat=4):
        fixed=np.array(states)!=1;active=~fixed;f=np.where(np.array(states)==2,cap,0.)
        if active.any():f[active]=np.linalg.solve(A[np.ix_(active,active)],b[active]-A[np.ix_(active,fixed)]@f[fixed])
        residual=A@f-b
        if (f>=-1e-5).all() and (f<=cap+1e-5).all() and (residual[np.array(states)==0]>=-1e-5).all() and (residual[np.array(states)==2]<=1e-5).all():expected=f;break
    assert expected is not None,name
    assert np.allclose(actual,expected,rtol=2e-4,atol=cap*2e-5),(name,dt,actual,expected)
    # The velocity correction from damping cannot add contact energy.
    work=dt*np.dot(actual,free)+.5*dt*dt*(actual@W@actual)
    assert work<=1e-6,(name,dt,'energy added',work)
    count+=1
assert count==len(profiles)*9
print(f'PASS {count} native wheel manifolds; bounded forces match independent solve; damping adds no energy')
