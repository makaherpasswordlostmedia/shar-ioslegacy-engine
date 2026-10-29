#!/usr/bin/env python3
"""Exercise actual parked-car save/restore and draw code against CAR1 hinges.

Old shared visual state must fail; the test observes actual matrices and damaged
texture selection, including a different model lift and independent body pose.
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse, json, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/camera'))
from chase_motion import function

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--old',action='store_true');ap.add_argument('levels',nargs='*',type=Path);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 main=read_main(ROOT/'viewer/main.c');gate=re.search(r'if \(ji [^\n]*?carjack\(ji, jp\);',main).group();save=function(main,'parkOwnCar');resume=function(main,'resumeOwnCar')
 start=main.index('    if (oldCarOn && haveCarVis && haveCol && !bpass && !inR)');end=main.index('    // персонажи:',start);draw=main[start:end]
 if a.old:
  save=save.replace('oldCv = *visual;', '(void)visual;')
  resume=resume.replace('cv = oldCv;', '')
  draw=draw.replace('&oldCv','&cv');gate=gate.replace(' || ji == -2','')
 code=r'''
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "pspgu.h"
#include "hinge_fixture.h"
static Car car,oldCar;static CarVis cv,oldCv;static int oldCarOn,haveCarVis=1,haveCol=1,bpass,inR;
typedef struct {int tex,pad[2],cell;float ox,oy,oz,sc;} Rec;
typedef struct {Rec r;} Piece;static Piece pc[4];static int carP[4]={0,1,2,3},ncarP=4;
static struct{int state;} cl[1]={{2}};static float ex,ez;
static float drawn[4][16];static int texture[4],drawN,checks,bad;
static void resetState(void){}
static void drawPieceM(Piece *d,const ScePspFMatrix4 *m){if(drawN<4){memcpy(drawn[drawN],m,64);texture[drawN++]=d->r.tex;}}
static void check(int ok,const char *why){checks++;if(!ok){bad++;printf("FAIL %s\n",why);}}
'''+save+'\n'+resume+'\nstatic int routed; static void carjack(int i,int p){(void)p;routed=i;}\nstatic void route(int ji){int jp=0;'+gate+'}\nstatic void drawParked(void){\n'+draw+'\n}\n'+r'''
int main(int argc,char **argv){
 routed=99;route(-2);check(routed==-2,"Triangle returns to parked own car");routed=99;route(-1);check(routed==99,"no nearby car does not summon");routed=99;route(0);check(routed==0,"traffic hijack retained");
 CarVis orig;if(!hingeFixture(&orig,argc>1?argv[1]:"build/ship_stage/level.shr")||orig.nhinge!=4)return 2;
 for(int pass=0;pass<3;pass++){
  cv=orig;car=(Car){0};carDefaults(&car.p);car.q[0]=cosf(.2f);car.q[2]=sinf(.2f);car.x=2;car.y=3;car.z=4;car.damage=pass==2?0.f:.8f;cv.prevDamage=car.damage;
  for(int j=0;j<4;j++){cv.th[j]=pass==2?0.f:cv.hinge[j].max*.55f;cv.thv[j]=pass==2?0.f:.12f*(j+1);cv.latched[j]=pass==2;cv.zoneDam[j]=pass==2?0.f:.3f;}
  Car parked=car;CarVis parkedVis=cv;
  // The world-car callback may change pLift before its successful return.
  if(pass==1)cv.lift+=1.1f;
  parkOwnCar(&parked,pass==1?&parkedVis:&cv);
  check(oldCarOn,"parked car exists");
  cv=orig;cv.lift+=2.3f;car.damage=pass==2?.8f:0.f;car.x=25;car.q[0]=1;car.q[2]=0;
  for(int f=0;f<30;f++){
   car.vel[0]=f*.7f;carVisUpdate(&cv,&car,NULL,1.f/30);
   for(int j=0;j<4;j++){
    pc[j].r=(Rec){.tex=orig.ndam?orig.dam[j%orig.ndam].texNorm:-1,.pad={orig.hinge[j].joint,0},.ox=.3f,.oy=-.2f,.oz=.5f,.sc=.8f};
   }
   drawN=0;drawParked();check(drawN==4,"all parked pieces drawn");
   for(int j=0;j<4;j++){
    float expect[16];carVisPieceMatrix(&parkedVis,&parked,pc[j].r.pad[0],0,.3f,-.2f,.5f,.8f,expect);
    float error=0;for(int k=0;k<16;k++)error=fmaxf(error,fabsf(drawn[j][k]-expect[k]));
    check(error<.00001f,"parked hinge/model matrix independent of driven car");
    check(texture[j]==carVisTex(&parkedVis,pc[j].r.tex),"parked damaged texture independent of driven car");
   }
  }
  resumeOwnCar();check(!oldCarOn,"parked slot released");check(!memcmp(&car,&parked,sizeof car),"body orientation, suspension and damage restored");
  parkedVis.motionValid=0;check(!memcmp(&cv,&parkedVis,sizeof cv),"original visual state restored before motion sample");
 }
 printf("%s parked visual checks=%d failures=%d\n",bad?"FAIL":"PASS",checks,bad);return !!bad;
}
'''
 src=a.out/'parked.c';src.write_text(code);core=a.out/'carvis_core.c';core.write_text((ROOT/'viewer/carvis.c').read_text().split('void carVisDrawShadow(')[0]);binary=a.out/'parked'
 subprocess.run(['cc','-std=c11','-O2','-I',str(ROOT/'viewer'),'-I',str(ROOT/'tests/wheels/stub'),'-I',str(ROOT/'tests/cars'),str(src),str(core),str(ROOT/'viewer/car.c'),str(ROOT/'viewer/col.c'),'-lm','-o',str(binary)],check=True)
 results=[]
 for level in a.levels or [ROOT/'build/ship_stage/level.shr']:
  r=subprocess.run([str(binary),str(level)],capture_output=True,text=True);print(str(level)+': '+(r.stdout.strip().splitlines() or [f'fixture unavailable rc={r.returncode}'])[-1]);results.append(dict(level=str(level),rc=r.returncode,result=r.stdout))
 (a.out/'report.json').write_text(json.dumps(results,indent=2)+'\n');return int(any(r['rc'] for r in results))
if __name__=='__main__':raise SystemExit(main())
