#!/usr/bin/env python3
"""Measured native tPointCamera b01 eye/lens, real production host and OLD."""
import json, subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2]; O=R/'build/gates/bonus_camera';O.mkdir(parents=True,exist_ok=True)
f=json.loads((R/'knowledge/facts/ps2-bonus-b01-native.yaml').read_text())
bind=f['camera_observation']['actual_binding']; ref=bind['race']
assert bind['red_caught'] and bind['states']==49 and ref['camera_rtti']['name']=='12tPointCamera'
for key in ['eye','target','up']: ref[key]=[ref[key][0],ref[key][1],-ref[key][2]]
fields={'eye':.001,'target':.001,'up':.00001,'vertical_fov_deg':.0001,'near_parameter':.001,'far_parameter':.001,'distance_eye_target':.001}
for mode in ['green','old']:
 exe=O/mode
 cmd=['cc','-std=c11','-O2','-w','-DSKIN_HOST','-I',str(R/'viewer')]
 if mode=='old':cmd+=['-DBONUS_CAMERA_PS2_OLD=1']
 cmd += [str(R/p) for p in ['tests/bonus/camera_host.c','viewer/bonus.c','viewer/msncar.c','viewer/car.c','viewer/col.c','viewer/traffic.c','viewer/homer.c','viewer/skin.c','viewer/props.c','viewer/stateprops.c','viewer/animobj.c','viewer/coins.c']]+['-lm','-o',str(exe)]
 subprocess.run(cmd,check=True)
 raw=subprocess.check_output([str(exe),str(R/'build/bonus-screens-stage/bonus/b01.bns')],text=True)
 (O/(mode+'.json')).write_text(raw);got=json.loads(raw)
 err={k:max(abs(x-y) for x,y in zip(got[k],ref[k])) if isinstance(got[k],list) else abs(got[k]-ref[k]) for k in fields}
 ok=all(err[k]<=tol for k,tol in fields.items());print(mode,err, 'GREEN' if ok else 'RED')
 assert ok==(mode=='green')
print('PASS native49 typed-camera facts / production helper / actual OLD red')
