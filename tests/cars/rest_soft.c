#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
static int sleeps;
void carRestSleepTest(const Car *c,int quiet){(void)c;sleeps+=quiet;}
static struct {ColHdr h;ColTri t[2];ColBox b;unsigned start[2],refs[3];} f;
int main(void){
 memset(&f,0,sizeof f);memcpy(f.h.magic,"COL1",4);f.h.ox=f.h.oz=-50;f.h.cell=100;f.h.W=f.h.H=1;f.h.ntri=2;f.h.nbox=1;f.h.nref=3;
 f.t[0]=(ColTri){{-50,-2,-50},{50,-2,50},{50,-2,-50},{0,1,0}};
 f.t[1]=(ColTri){{-50,-2,-50},{-50,-2,50},{50,-2,50},{0,1,0}};
 f.b=(ColBox){{0,-1,0},{1,0,0},{0,1,0},{0,0,1},{30,1,30},0};f.start[1]=3;f.refs[0]=0;f.refs[1]=1;f.refs[2]=COL_BOX<<29;
 int failed=0;
 for(int soft=0;soft<2;soft++){
  f.b.pad=soft?COL_MAT_FOLIAGE:COL_MAT_HARD;ColWorld w;if(colInit(&w,&f,sizeof f))return 2;
  CarParams p;carParamsFor("marge_v",&p);Car c;carInit(&c,&p,&w,0,1,0,0);CarInput in={0};sleeps=0;
  for(int i=0;i<600;i++)carUpdate(&c,&w,&in,1.f/60);int idle=sleeps;printf("support soft=%d idleSleep=%d cover=%.3f wheels=%d\n",soft,idle,c.foliCover,c.wheels);
  if(soft?!!idle:!idle)failed++;
  for(int mode=0;mode<3;mode++){
   sleeps=0;in=(CarInput){0};if(mode==0)in.throttle=1;else if(mode==1)in.brake=1;else in.handbrake=1;
   carUpdate(&c,&w,&in,1.f/60);printf("wake soft=%d mode=%d firstFrameSleep=%d\n",soft,mode,sleeps);failed+=!!sleeps;
  }
  colFree(&w);
 }
 printf("%s rest soft guard failures=%d\n",failed?"FAIL":"PASS",failed);return failed?1:0;
}
