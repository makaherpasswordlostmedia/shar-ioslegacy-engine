#!/usr/bin/env python3
"""Compile the actual chaseCamUpdate from main.c; test moving-target prediction.

All disc FollowCamera profiles, 30/60/120 Hz, slopes and a ballistic arc.
The collision stub observes the ray origin contract, not world geometry.
--source permits an unchanged old main.c as a negative control.
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def function(src, name):
    match = re.search(r'^static [^\n;=]+\b' + name + r'\([^\n]*\)\s*\{', src, re.M)
    if not match:
        raise ValueError('Function declaration not found: ' + name)
    start = match.start()
    opening = match.end() - 1
    depth = 1
    end = opening + 1
    while depth:
        depth += (src[end] == '{') - (src[end] == '}')
        end += 1
    return src[start:end]


HARNESS = r'''
static int checks, bad;
static void check(int ok, const char *what) {
  checks++; if (!ok) { bad++; printf("FAIL %s\n", what); }
}
int main(void) {
  float worst = 0.f, worstArc = 0.f, worstSpin = 0.f, worstYawJump = 0.f;
  for (int model = 0; model < CAR_CAMS; model++) for (int hz = 30; hz <= 120; hz *= 2) {
    Car c = {0}; float cam[3], look[3], dt = 1.f / hz;
    strncpy(c.p.name, carCamTab[model].name, sizeof c.p.name - 1);
    c.p.bodyHi = 1.65f; c.p.halfL = 2.675f; c.p.bodyOfs = -.32f;
    c.p.camElev = 1.23f; c.p.camMag = 7.2f;
    for (int arc = 0; arc < 2; arc++) {
      memset(&chase, 0, sizeof chase); haveCol = 0;
      float lag = 0.f;
      for (int f = 0; f <= hz * 2; f++) {
        float t = f * dt;
        c.z = 40.f * t; c.vel[2] = 40.f;
        c.y = 100.f + (arc ? 14.f * t - 7.5f * t * t : 14.f * t);
        c.vel[1] = arc ? 14.f - 15.f * t : 14.f;
        chaseCamUpdate(&c, 0.f, dt, cam, look);
        float e = fabsf(look[1] - (c.y + chaseInfo.tgtY));
        if (e > lag) lag = e;
        check(isfinite(cam[0]) && isfinite(cam[1]) && isfinite(cam[2]), "finite camera");
      }
      if (arc) { if (lag > worstArc) worstArc = lag; }
      else if (lag > worst) worst = lag;
      check(lag < .05f, arc ? "ballistic prediction within 5 cm" : "ramp ascent prediction within 5 cm");
    }
    haveCol = 1; rays = 0;
    chaseCamUpdate(&c, 0.f, dt, cam, look);
    check(rays == 5, "all five unobstructed collision rays observed");
    for (int k = 0; k < 3; k++) check(fabsf(rayTarget[k] - look[k]) < .0001f, "collision uses rendered target");
    // A positional jolt still decays through the error spring; it is not a teleport.
    haveCol = 0; memset(&chase, 0, sizeof chase); c.y = 100.f; c.vel[1] = 0.f;
    chaseCamUpdate(&c, 0.f, dt, cam, look); float before = look[1];
    c.y += .5f; chaseCamUpdate(&c, 0.f, dt, cam, look);
    check(look[1] - before < .49f && look[1] >= before, "jolt remains smoothed");
    for (int f = 0; f < hz * 3; f++) chaseCamUpdate(&c, 0.f, dt, cam, look);
    check(fabsf(look[1] - c.y - chaseInfo.tgtY) < .001f, "jolt settles");
    // Uniform anchor motion with a rotating offset COM. Its velocity is
    // prescribed from analytic X/Y/Z rotations, independently of car.c.
    // A body spin must not be mistaken for motion of the camera's anchor.
    for(int axis=0;axis<3;axis++) {
      memset(&chase,0,sizeof chase);float lag=0;
      c.com[0]=.15f;c.com[1]=.7f;c.com[2]=.4f;c.h=0;
      for(int f=0;f<=hz*2;f++) {
        float t=f*dt,a=6.f*t,C=cosf(a),S=sinf(a);float r[3];
        if(axis==0){r[0]=c.com[0];r[1]=C*c.com[1]-S*c.com[2];r[2]=S*c.com[1]+C*c.com[2];}
        else if(axis==1){r[0]=C*c.com[0]+S*c.com[2];r[1]=c.com[1];r[2]=-S*c.com[0]+C*c.com[2];}
        else{r[0]=C*c.com[0]-S*c.com[1];r[1]=S*c.com[0]+C*c.com[1];r[2]=c.com[2];}
        memset(c.q,0,sizeof c.q);c.q[0]=cosf(a*.5f);c.q[axis+1]=sinf(a*.5f);
        memset(c.w,0,sizeof c.w);c.w[axis]=6.f;
        c.x=0;c.y=100+14*t;c.z=40*t;c.vel[0]=0;c.vel[1]=14;c.vel[2]=40;
        c.vel[(axis+1)%3]-=6.f*r[(axis+2)%3];c.vel[(axis+2)%3]+=6.f*r[(axis+1)%3];
        chaseCamUpdate(&c,0,dt,cam,look);
        float d[3]={look[0],look[1]-c.y-chaseInfo.tgtY,look[2]-c.z-chaseInfo.tgtF};
        float error=sqrtf(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]);if(error>lag)lag=error;
      }
      if(lag>worstSpin)worstSpin=lag;check(lag<.05f,"body rotation does not move camera anchor");
    }
    // An impact can change projected heading abruptly. The camera should
    // start turning smoothly instead of jumping most of that angle at once.
    memset(&chase,0,sizeof chase);memset(c.w,0,sizeof c.w);memset(c.vel,0,sizeof c.vel);c.h=0;
    chaseCamUpdate(&c,0,dt,cam,look);c.h=2.f;chaseCamUpdate(&c,0,dt,cam,look);
    float jump=fabsf(chase.yaw);if(jump>worstYawJump)worstYawJump=jump;
    check(jump<.1f,"impact heading does not snap camera to the other side");
    for(int f=0;f<hz*3;f++)chaseCamUpdate(&c,0,dt,cam,look);
    check(fabsf(wrapPi(chase.yaw-c.h))<.001f,"impact heading tracking settles");
  }
  printf("profiles=%d ramp_lag=%.4f arc_lag=%.4f spin_lag=%.4f first_yaw_jump=%.4f checks=%d failures=%d\n", CAR_CAMS, worst, worstArc, worstSpin,worstYawJump,checks, bad);
  return bad ? 1 : 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'viewer/main.c')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/codex-terminal/rob-pack/388-camera/host')
    args = parser.parse_args()
    src = read_main(args.source)
    defines = '\n'.join(re.findall(r'^#define CAM_[A-Z0-9_]+\s+[^\n]+', src, re.M))
    state = re.search(r'typedef struct \{ int init;.*?\} ChaseCam;', src).group()
    info = re.search(r'typedef struct \{ const char \*name; int ps2;.*?\} ChaseInfo;', src).group()
    preamble = r'''
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "car.h"
#include "carcam.h"
#define GU_PI 3.14159265f
#define FOVY 62.f
#define ASPECT (480.f/272.f)
#define NEAR_Z .7f
static int gameLevel=1, haveCol, chaseOld, chaseLevelOld, camHighOld, camGroundOld, chaseWallOff;
static ColWorld world;
static float chaseNear;
static struct {float lift;} cv;
static int rays; static float rayTarget[3];
static int ground(float x,float z,float top,float bottom,float *g) { (void)x;(void)z;(void)top;(void)bottom;(void)g; return 0; }
static float mockRayFrac(const ColWorld *w,const float *t,const float *e,int flags) {
  (void)w;(void)e;(void)flags; memcpy(rayTarget,t,12); rays++; return 1.f;
}
static float camCarsFrac(const float *t,const float *e) {(void)t;(void)e;return 1.f;}
#define colRayFrac mockRayFrac
'''
    code = preamble + defines + '\n' + state + '\nstatic ChaseCam chase;\n' + info + '\nstatic ChaseInfo chaseInfo;\n'
    code += '\n'.join(function(src, f) for f in ('cdStep', 'wrapPi', 'carCamFind', 'camFit', 'chaseCamUpdate')) + HARNESS
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cfile = args.out.with_suffix('.c')
    cfile.write_text(code)
    subprocess.run(['cc', '-std=c11', '-O2', '-DSKIN_HOST', '-I', str(ROOT / 'viewer'), str(cfile), str(ROOT/'viewer/car.c'),str(ROOT/'viewer/col.c'), '-lm', '-o', str(args.out)], check=True)
    return subprocess.run([str(args.out)]).returncode


if __name__ == '__main__':
    raise SystemExit(main())
