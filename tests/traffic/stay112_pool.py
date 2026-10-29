#!/usr/bin/env python3
"""Actual trafficUpdate cull/refill, real no-cull source mutation must fail"""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/traffic-rejoin';OUT.mkdir(exist_ok=True)
source=(ROOT/'viewer/traffic.c').read_text();needle='if (d > REMOVE_HARD || (d > REMOVE_R && !seen) || (c->next < 0 && c->v < .1f && !seen)) c->mode = TRM_OFF;'
assert source.count(needle)==1
bad=OUT/'no-cull.c';bad.write_text(source.replace(needle,'if (0) c->mode = TRM_OFF;'))
codes={}
for side,traffic in [('new',ROOT/'viewer/traffic.c'),('no-cull',bad)]:
 exe=OUT/('pool-'+side)
 subprocess.run(['cc','-std=c11','-O2','-w','-DSKIN_HOST','-Iviewer','tests/traffic/stay112_pool.c',traffic,'viewer/homer.c','viewer/skin.c','viewer/col.c','viewer/car.c','-lm','-o',exe],cwd=ROOT,check=True)
 r=subprocess.run([exe],cwd=ROOT,capture_output=True,text=True);(OUT/('pool-'+side+'.log')).write_text(r.stdout+r.stderr);print(side,'rc',r.returncode,r.stdout[-500:]);codes[side]=r.returncode
assert codes=={'new':0,'no-cull':1}
print('PASS actual ten collisions/culling/refill; actual source without culling RED')
