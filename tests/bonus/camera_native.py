#!/usr/bin/env python3
"""Actual PSP draw-camera parameters versus typed PS2 b01 eye/lens; OLD red."""
import json,sys
from pathlib import Path
import unlock_emu as U
U.OUT=U.ROOT/'build/gates/bonus_camera';U.OUT.mkdir(parents=True,exist_ok=True)
red='--red' in sys.argv; args=[a for a in sys.argv[1:] if a!='--red']
scen='flag menu\nflag bonusopen\nflag bonusshots 1\nflag bonusauto 1\nwait 2\npress left\nwait .6\npress cross\nwait 2\nflag bonusgo\nwait 13\nend\n'
d,bad=U.run('native-old' if red else 'native-green',Path(args[0]).resolve(),scen,timeout=240)
rows=[U.kv(l) for l in U.lines(d) if l.startswith('BONUS ev=topcamera track=1 ')]
ref=json.loads((U.ROOT/'knowledge/facts/ps2-bonus-b01-native.yaml').read_text())['camera_observation']['actual_binding']['race']
for key in ['eye','target','up']: ref[key]=[ref[key][0],ref[key][1],-ref[key][2]]
err=[]
for e in rows:
 for key,nkey in [('eye','eye'),('at','target'),('up','up')]: err.append(max(abs(x-y) for x,y in zip(map(float,e[key].split(',')),ref[nkey])))
 for key,nkey in [('fovy','vertical_fov_deg'),('near','near_parameter'),('far','far_parameter'),('dist','distance_eye_target')]: err.append(abs(float(e[key])-ref[nkey]))
ok=bool(rows) and max(err)<.001
print('native:',d,'rows:',len(rows),'maximum camera difference:',max(err) if err else 'NO DATA','runner:',bad or 'END/errors0')
if red:
 caught=bool(rows) and not ok and not bad;print('RED CAUGHT' if caught else 'RED NOT CAUGHT');sys.exit(0 if caught else 1)
print('PASS native true b01 camera' if ok and not bad else 'FAIL native true b01 camera');sys.exit(0 if ok and not bad else 1)
