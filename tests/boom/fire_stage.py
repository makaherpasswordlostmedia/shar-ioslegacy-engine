#!/usr/bin/env python3
"""Actual main.c emitter block and car physics: mobile damage smokes, lethal damage burns.

Reference: native a355_boom frames 3340/3370 (mobile, smoke),
3400/3490 (stopped, flame and ejected Homer), 3530 (explosion).
The old production block must fail; no emitter or physics implementation is copied.
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def emitter_block(source):
    start = source.index('{ // дым/огонь: родная система')
    end = source.index('static int wasBoomed;', start)
    return source[start:end]


HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static Car car;
static float rates[3]; static int husk, checks, fails;
static int fxAlive(int h) { return h!=0; }
static int fxFindInst(int i) { return i; }
static int fxStartSystem(int i,const float *p,const float *m) { (void)p;(void)m;if(i==19)husk=1;return i; }
static void fxMove(int h,const float *p,const float *m) {(void)h;(void)p;(void)m;}
static void fxStop(int h) { if(h==14)memset(rates,0,sizeof rates);if(h==19)husk=0; }
static void fxSetEmitRate(int h,int i,float rate) { if(h==14&&i<3)rates[i]=rate; }
static void effects(void) { float hx=0,hy=0,hz=0; @BLOCK@ }
static void check(int ok,const char*why) {checks++;if(!ok){fails++;printf("FAIL %s damage=%.4f dead=%d time=%.3f rates=%.1f/%.1f/%.1f\n",why,car.damage,car.destroyed,car.deadT,rates[0],rates[1],rates[2]);}}
int main(int argc,char**argv) {
 if(argc!=2)return 2;
 FILE*f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);unsigned n=ftell(f);rewind(f);
 unsigned char*d=aligned_alloc(16,(n+15)&~15u);if(fread(d,1,n,f)!=n)return 2;fclose(f);
 unsigned co=*(unsigned*)(d+92),po=*(unsigned*)(d+96),pv=*(unsigned*)(d+88),ce=n;
 if(po>co&&po<ce)ce=po;if(pv>co&&pv<ce)ce=pv;
 ColWorld w;if(colInit(&w,d+co,ce-co))return 2;
 float g;if(!colGround(&w,220,172,50,-50,&g,0))return 2;
 carInit(&car,NULL,&w,220,g,172,1.5708f);
 for(int i=0;i<=1000;i++){
  car.damage=i/1000.f;car.destroyed=i==1000;effects();
  check((rates[1]>0)==car.destroyed && (rates[2]>0)==car.destroyed,"flame matches lethal damage, not smoke warning");
  check((rates[0]>0)==(i>=330),"smoke retained");
 }
 car.damage=.99f;car.destroyed=0;effects();
 float x=car.x,z=car.z;CarInput in={1,0,.5f,0};
 for(int i=0;i<30;i++) {carUpdate(&car,&w,&in,1/60.f);effects();check(!rates[1]&&!rates[2],"mobile damaged car has no lethal flame");}
 check(hypotf(car.x-x,car.z-z)>.2f && !car.destroyed,"damaged car remains controllable");
 carSetSpeed(&car,0);car.damage=1;car.destroyed=1;effects();
 check(rates[1]>0&&rates[2]>0&&!husk,"lethal flame begins before explosion");
 x=car.x;z=car.z;
 for(int i=1;i<=180;i++){carUpdate(&car,&w,&in,1/60.f);effects();check(rates[1]>0&&rates[2]>0,"flame stays on during destruction delay");if(i<174)check(!husk,"no early husk fire");}
 check(hypotf(car.x-x,car.z-z)<.3f,"burning car ignores throttle");
 for(int i=0;i<6;i++)carUpdate(&car,&w,&in,1/60.f);effects();
 check(carBoomed(&car)&&husk,"explosion starts husk fire");
 car.damage=0;car.destroyed=0;effects();
 check(!husk&&!rates[0]&&!rates[1]&&!rates[2],"repair clears smoke and flame");
 printf("%s fire stage checks=%d failures=%d\n",fails?"FAIL":"PASS",checks,fails);return fails?1:0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='build/fire-stage')
    ap.add_argument('--level', default='build/level.shr')
    a = ap.parse_args()
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    old = subprocess.check_output(['git', 'show', 'a576255:viewer/main.c'], cwd=ROOT, text=True)
    for name, source, expected in [('green', read_main(ROOT/'viewer/main.c'), 0), ('old', old, 1)]:
        c = out / (name+'.c')
        c.write_text(HARNESS.replace('@BLOCK@', emitter_block(source)))
        exe = out / name
        subprocess.run(['cc', '-std=c11', '-O2', '-I', str(ROOT/'viewer'), str(c),
                        str(ROOT/'viewer/car.c'), str(ROOT/'viewer/col.c'), '-lm', '-o', str(exe)], check=True)
        r = subprocess.run([str(exe), str(ROOT/a.level)], text=True, capture_output=True)
        (out/(name+'.log')).write_text(r.stdout+r.stderr)
        print(r.stdout.splitlines()[-1] if r.stdout else r.stderr)
        if r.returncode != expected:
            raise SystemExit('Unexpected actual emitter/physics gate result')
        if name == 'old' and 'FAIL mobile damaged car has no lethal flame' not in r.stdout:
            raise SystemExit('Old block did not fail the reported gameplay problem')
    print('PASS actual main.c damage effects and controllability; old early flame rejected')


if __name__ == '__main__':
    main()
