#include <stdio.h>
#include <math.h>
#include <string.h>
#include "car.h"
#include "carparams.h"
// Actual carUpdate on a road at the last instant of a valid landing
// Native tuning, family geometry: this tests the reset timer, not a full jump
static struct { ColHdr h; ColTri t[2]; unsigned start[2],refs[2]; } floorData;
int main(void) {
 memset(&floorData,0,sizeof floorData); memcpy(floorData.h.magic,"COL1",4);
 floorData.h.ox=floorData.h.oz=-100;floorData.h.cell=200;floorData.h.W=floorData.h.H=1;floorData.h.ntri=floorData.h.nref=2;
 floorData.t[0]=(ColTri){{-100,0,-100},{100,0,100},{100,0,-100},{0,1,0}};
 floorData.t[1]=(ColTri){{-100,0,-100},{-100,0,100},{100,0,100},{0,1,0}};
 floorData.start[1]=2;floorData.refs[0]=0;floorData.refs[1]=1;
 ColWorld w;if(colInit(&w,&floorData,sizeof floorData))return 2;
 int bad=0,cases=0;CarInput in={0};
 const float loss[]={5,25,55};const int hz[]={30,60,120};
 for(int m=0;m<CAR_CONS;m++)for(int h=0;h<3;h++)for(int d=0;d<3;d++) {
  CarParams p;if(!carParamsFor(carCons[m].name,&p))return 2;
  Car c;carInit(&c,&p,&w,0,0,0,0);float dt=1.f/hz[h];
  for(int i=0;i<hz[h];i++)carUpdate(&c,&w,&in,dt);
  int before=c.recoveries;
  c.fallTop=c.y+loss[d];c.fallT0=c.t;c.grounded=0;c.y+=.01f;c.vel[1]=-1;
  int peak=0;for(int i=0;i<2*hz[h];i++){carUpdate(&c,&w,&in,dt);if(c.fallPending)peak=1;}
  int fail=c.recoveries!=before || peak || !c.grounded;
  if(fail)printf("FAIL %s %dHz loss=%.0f resets=%d pending=%d wheels=%d ground=%d\n",p.name,hz[h],loss[d],c.recoveries-before,peak,c.wheels,c.grounded);
  bad+=fail;cases++;
 }
 // Full 25 m ballistic drop, with actual wheel/body collision and response
 for(int m=0;m<CAR_CONS;m++)for(int h=0;h<3;h++) {
  CarParams p;if(!carParamsFor(carCons[m].name,&p))return 2;
  Car c;carInit(&c,&p,&w,0,0,0,0);float dt=1.f/hz[h];
  c.y+=25;c.fallTop=c.y;c.fallT0=c.t;c.grounded=0;c.vel[1]=-1;
  int air=0,landed=0,pending=0;
  for(int i=0;i<5*hz[h];i++) {carUpdate(&c,&w,&in,dt);air|=!c.grounded;if(air&&c.grounded)landed=1;pending|=c.fallPending;}
  int fail=c.recoveries || pending || !landed || !c.grounded || fabsf(c.y)>.1f;
  if(fail)printf("FAIL full drop %s %dHz resets=%d pending=%d landed=%d ground=%d y=%.3f\n",p.name,hz[h],c.recoveries,pending,landed,c.grounded,c.y);
  bad+=fail;cases++;
 }
 // Missing world still recovers, independently of height-only landing rule
 floorData.h.ox=floorData.h.oz=200;
 for(int i=0;i<2;i++)for(int v=0;v<3;v++) {
  float *pt=v==0?floorData.t[i].a:v==1?floorData.t[i].b:floorData.t[i].c;
  pt[0]+=300;pt[2]+=300;
 }
 ColWorld empty;if(colInit(&empty,&floorData,sizeof floorData))return 2;
 Car c;carInit(&c,NULL,&empty,0,25,0,0);
 for(int i=0;i<180;i++)carUpdate(&c,&empty,&in,1/60.f);
 int protected=c.recoveries>0 && isfinite(c.y);bad+=!protected;
 printf("%s native tuning=%d landing cases=%d failures=%d void recovery=%d\n",bad?"FAIL":"PASS",CAR_CONS,cases,bad,c.recoveries);
 return !!bad;
}
