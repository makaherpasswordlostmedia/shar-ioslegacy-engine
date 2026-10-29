/* Four real vehicle parameter sets, 7 step heights, 4 approach speeds.
   Below the configured 35 cm step: cross; 40 cm / 1 m / 2 m: remain blocked. */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
int main(void){int bad=0,checks=0;
 for(int model=0;model<4;model++)for(int h=1;h<=7;h++)for(int s=0;s<4;s++){
 float height=(float[]){.1f,.2f,.3f,.34f,.4f,1.f,2.f}[h-1],speed=(float[]){0,10,30,60}[s];
 struct {ColHdr h;ColTri t[2];ColBox b;unsigned start[2],ref[3];}f={0};
 memcpy(f.h.magic,"COL1",4);f.h.ox=f.h.oz=-100;f.h.cell=200;f.h.W=f.h.H=1;f.h.ntri=2;f.h.nbox=1;f.h.nref=3;
 f.t[0]=(ColTri){{-100,0,-100},{100,0,100},{100,0,-100},{0,1,0}};f.t[1]=(ColTri){{-100,0,-100},{-100,0,100},{100,0,100},{0,1,0}};
 f.b=(ColBox){{0,height/2,15},{1,0,0},{0,1,0},{0,0,1},{30,height/2,15},0};f.start[1]=3;f.ref[1]=1;f.ref[2]=COL_BOX<<29;
 ColWorld w;if(colInit(&w,&f,sizeof f))return 2;const char*names[]={"famil_v","sportsa","pickupa","schoolbu"};CarParams pp;if(!carParamsFor(names[model],&pp))return 3;Car c;carInit(&c,&pp,&w,0,0,-7,0);CarInput in={0};for(int n=0;n<30;n++)carUpdate(&c,&w,&in,1/60.f);carSetSpeed(&c,speed/3.6f);in.throttle=1;
 float maxy=0;for(int n=0;n<300;n++){carUpdate(&c,&w,&in,1/60.f);maxy=fmaxf(maxy,c.y);}
 printf("%s height %.2f speed %.0f z %.3f y %.3f maxY %.3f speedEnd %.2f walls %u\n",names[model],height,speed,c.z,c.y,maxy,c.v,c.contacts);int ok=isfinite(c.z)&&isfinite(c.y)&&(height<.35f?c.z>5.f:c.z<0.f);checks++;bad+=!ok;colFree(&w);
 }
 printf("%s checks=%d bad=%d\n",bad?"FAIL":"PASS",checks,bad);return bad?1:0;
}
