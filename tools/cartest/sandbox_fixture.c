// Independent fixture: two physical floors at the same XZ, a real falling car,
// and actual peer collision. No PSP/emulator dependency.
#include "../../viewer/car.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
int main(void){
  struct {ColHdr h;ColTri t[4];unsigned start[2],refs[4];} f={0};
  memcpy(f.h.magic,"COL1",4);f.h.ox=f.h.oz=-40;f.h.cell=80;f.h.W=f.h.H=1;f.h.ntri=f.h.nref=4;
  for(int l=0;l<2;l++){
    float y=l*4.f;
    f.t[l*2]=(ColTri){{-40,y,-40},{40,y,40},{40,y,-40},{0,1,0}};
    f.t[l*2+1]=(ColTri){{-40,y,-40},{-40,y,40},{40,y,40},{0,1,0}};
  }
  f.start[1]=4;for(int i=0;i<4;i++)f.refs[i]=(unsigned)i;
  ColWorld w;if(colInit(&w,&f,sizeof f))return 2;
  float y=-99;if(!colGround(&w,0,0,10,-10,&y,0)||fabsf(y-4)>.001f)return 1;
  if(!colGround(&w,0,0,y-.12f,-10,&y,0)||fabsf(y)>.001f)return 1;
  if(colGround(&w,0,0,-.12f,-10,&y,0))return 1;
  Car c;carInit(&c,0,&w,0,4,0,0);c.y+=5;c.vel[1]=-3;
  CarInput in={0};int air=0,land=0;
  for(int i=0;i<240;i++){carUpdate(&c,&w,&in,1.f/60);air|=!c.grounded;if(air&&c.grounded)land=1;if(!isfinite(c.y)||c.y<3.7f)return 1;}
  if(!air||!land||fabsf(c.y-4)>.2f||c.recoveries)return 1;
  Car a,b;carInit(&a,0,&w,0,4,0,0);carInit(&b,0,&w,0,4,4,3.14159265f);carSetSpeed(&a,10);carSetSpeed(&b,10);
  if(!carHitCar(&a,&b,&w))return 1;
  if(a.vel[2]>=9.9f||b.vel[2]<=-9.9f)return 1;
  printf("PASS two stacked supports, real flight/roof landing, opposing-car impulse\n");colFree(&w);return 0;
}
