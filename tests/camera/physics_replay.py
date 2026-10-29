#!/usr/bin/env python3
"""Run real car physics and production follow-camera safety on one saved pose.

The pose is the input of tests/cars/native_replay.py. COL1, the SHR7 height map,
car.c, chaseCamUpdate, camSafeEye and camsafe.c run together at PAL 50 Hz.
The scene contains the player's car and the static city; traffic, NPCs and
authored cutscene cameras are outside this probe. This is a camera geometry
check, not acceptance of the vehicle's trajectory against the PS2 original.
--plant eye-in-car deliberately corrupts the final eye; it must fail.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np
from chase_motion import ROOT, function

PREAMBLE = r'''
#include <float.h>
#include "carcam.h"
#include "camsafe.h"
#define GU_PI 3.14159265f
#define FOVY 62.f
#define ASPECT (480.f/272.f)
#define NEAR_Z 1.5f
static int gameLevel=1,haveCol=1,chaseOld,chaseLevelOld,camHighOld,camGroundOld,chaseWallOff;
static ColWorld world;static float chaseNear;static struct {float lift;} cv;
static float hox,hoz,hcell;static int hw,hh;static short *hm;
// No other actors are spawned in this replay. The real safety scene below
// still includes the player's body, and every static-world ray is col.c.
static float camCarsFrac(const float*a,const float*b){(void)a;(void)b;return 1.f;}
static CsScene csScene;static float camPivot[3];static int camPivotCar=1;static const Car *subject;
static void camSafeScene(const float e[3],float R){
 (void)e;(void)R;csScene.w=&world;csScene.nbox=1;csScene.ncyl=0;
 CarBox cb;memset(&cb,0,sizeof cb);carBox(subject,&cb);CsBox *b=&csScene.box[0];
 b->x=cb.x;b->z=cb.z;b->fx=cb.fx;b->fz=cb.fz;b->hw=cb.hw;b->hl=cb.hl;
 b->y=cb.y;b->gx=cb.gx;b->gz=cb.gz;b->lo=cb.lo;b->hi=cb.hi;
}
'''

FRAME = r'''
  subject=&c;cv.lift=c.p.modelLift;float cam[3],look[3];chaseCamUpdate(&c,0,1/50.f,cam,look);
  CarBox cb;memset(&cb,0,sizeof cb);carBox(&c,&cb);camPivot[0]=cb.x;camPivot[1]=cb.y+cb.hi+.3f;camPivot[2]=cb.z;
  camSafeEye(cam,look,FOVY,1/50.f);
  /* PLANT */
  float forward[3]={look[0]-cam[0],look[1]-cam[1],look[2]-cam[2]};
  float length=sqrtf(forward[0]*forward[0]+forward[1]*forward[1]+forward[2]*forward[2]);
  for(int k=0;k<3;k++)forward[k]/=length;
  float tv=tanf(FOVY*GU_PI/360.f),near=csNearFree(&csScene,cam,forward,tv,tv*ASPECT,NEAR_Z);
  near=fmaxf(CS_NEAR_MIN,fminf(chaseNear,near));
  int flags=csProbe(&csScene,cam,forward,tv,tv*ASPECT,near,camPivot);
  float jump=fr?camEyeStep(cam,camPivot,previous,oldPivot,1):0;
  // Float additions/subtractions at world coordinates can exceed an exact
  // 0.5m step by a few micrometers. Budget arithmetic rounding per sample,
  // proportional to its operands, instead of relaxing the physical limit.
  float rounding=0.f;
  for(int k=0;k<3;k++){float b=4.f*FLT_EPSILON*(fabsf(cam[k])+fabsf(previous[k])+fabsf(camPivot[k])+fabsf(oldPivot[k]));rounding+=b*b;}
  rounding=sqrtf(rounding);
  fprintf(stderr,"%d %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d %.9g %d %.9g\n",
    fr,cam[0],cam[1],cam[2],look[0],look[1],look[2],near,chase.yaw,flags,jump,csWhyPick,rounding);
  memcpy(previous,cam,12);memcpy(oldPivot,camPivot,12);
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--level', type=Path, required=True)
    ap.add_argument('--pose', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--source', type=Path, default=ROOT / 'viewer/main.c')
    ap.add_argument('--car', type=Path, default=ROOT / 'viewer/car.c')
    ap.add_argument('--plant', choices=['eye-in-car'])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    src = args.source.read_text()
    replay = (ROOT / 'tests/cars/native_replay.c').read_text()
    state = re.search(r'typedef struct \{ int init;.*?\} ChaseCam;', src).group()
    info = re.search(r'typedef struct \{ const char \*name; int ps2;.*?\} ChaseInfo;', src).group()
    defines = '\n'.join(re.findall(r'^#define (?:CAM_|CS_)[A-Z0-9_]+\s+[^\n]+', src, re.M))
    safety = src[src.index('static float csOfs[3]'):src.index('// Правка 331: кадр камеры игры')]
    code = '#include <stdio.h>\n#include <stdlib.h>\n#include "' + str(args.car.resolve()) + '"\n'
    code += PREAMBLE + defines + '\n' + state + '\nstatic ChaseCam chase;\n'
    code += info + '\nstatic ChaseInfo chaseInfo;\n'
    code += '\n'.join(function(src, name) for name in (
        'ground','cdStep','wrapPi','carCamFind','camFit','chaseCamUpdate','camEyeStep')) + '\n' + safety
    replay = replay[replay.index('int main('):]
    replay = replay.replace('V3 cv=add', 'V3 nativeVelocity=add')
    for axis in 'xyz': replay = replay.replace('cv.'+axis, 'nativeVelocity.'+axis)
    init = 'if(colInit(&W,d+co,end-co))return 2;'
    assert init in replay
    replay = replay.replace(init, init + r'''
world=W;memcpy(&hox,d+56,4);memcpy(&hoz,d+60,4);memcpy(&hcell,d+64,4);
memcpy(&hw,d+68,4);memcpy(&hh,d+72,4);if(hw<=0||hh<=0||104u+8u*hw*hh>(unsigned)size)return 2;hm=(short*)(d+104);
''')
    replay = replay.replace(' for(int fr=0;fr<=frames;fr++) {',
                           ' float previous[3]={0},oldPivot[3]={0};\n for(int fr=0;fr<=frames;fr++) {')
    frame = FRAME
    if args.plant:
        frame = frame.replace('/* PLANT */', 'cam[0]=cb.x;cam[1]=cb.y+(cb.lo+cb.hi)*.5f;cam[2]=cb.z;')
    hook = '  if(fr%2)continue;M3 Q='
    assert hook in replay
    replay = replay.replace(hook, frame + hook)
    cfile = args.out / 'coupled.c'
    cfile.write_text(code + replay)
    exe = args.out / 'coupled'
    subprocess.run(['cc','-std=c11','-O2','-DSKIN_HOST','-I',str(ROOT/'viewer'),str(cfile),
                    str(ROOT/'viewer/col.c'),str(ROOT/'viewer/camsafe.c'),'-lm','-o',str(exe)], check=True)
    with (args.out/'vehicle.tsv').open('w') as vehicle, (args.out/'camera.tsv').open('w') as camera:
        subprocess.run([str(exe.resolve()),str(args.level.resolve()),str(args.pose.resolve())],
                       stdout=vehicle,stderr=camera,check=True)
    a = np.loadtxt(args.out/'camera.tsv', ndmin=2)
    assert len(a)>=3 and a.shape[1]==13, 'incomplete camera replay'
    bad = a[(a[:,9].astype(int)&31)!=0]
    report = dict(frames=len(a), nonfinite=int((~np.isfinite(a)).sum()),
                  inside_frames=len(bad), max_relative_eye_jump=float(a[:,10].max()),
                  min_near=float(a[:,7].min()), plant=args.plant, bad_rows=bad.tolist(),
                  max_rounding_bound=float(a[:,12].max()),
                  excessive_step_rows=a[a[:,10]>.5+a[:,12]].tolist(),
                  max_jump_row=a[a[:,10].argmax()].tolist(),
                  limits=dict(relative_eye_step_m=.5, near_min_m=.25),
                  scope='one vehicle plus static city; not native trajectory/camera equivalence')
    files = [args.level,args.pose,args.source,args.car,ROOT/'viewer/col.c',ROOT/'viewer/camsafe.c']
    report['sha256'] = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    report['passed'] = not report['nonfinite'] and not len(bad) and not report['excessive_step_rows'] and report['min_near']>=.25
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k not in ('bad_rows','sha256','excessive_step_rows')})
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
