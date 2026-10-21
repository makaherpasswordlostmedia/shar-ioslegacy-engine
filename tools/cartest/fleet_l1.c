// №388: разгон/торможение/руль машин порта на ровной улице L1. Сборка: cc -std=c11 -O2 -I viewer tools/cartest/fleet_l1.c viewer/car.c viewer/col.c -lm -o fleet; запуск: ./fleet build/level.shr famil_v bart_v ...
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "col.h"
int main(int argc,char **argv){
  FILE *f=fopen(argv[1],"rb");fseek(f,0,SEEK_END);unsigned n=ftell(f);rewind(f);unsigned char *b=malloc(n);
  if(fread(b,1,n,f)!=n)return 2;fclose(f);
  unsigned co=*(unsigned*)(b+92),po=*(unsigned*)(b+96),pv=*(unsigned*)(b+88),end=n;
  if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;
  ColWorld w;if(colInit(&w,b+co,end-co))return 2;
  printf("car\tv@100m_kmh\tt0_60\tt0_90\tbrake14_m\tbrake_from_v100_m\tyaw14_dps\tpitch_brk\tmaxlift_air_s\tmaxVy\n");
  for(int a=2;a<argc;a++){
    CarParams p;carParamsFor(argv[a],&p);float y;
    if(!colGround(&w,100.f,265.f,10,-10,&y,0))return 3;
    Car c;carInit(&c,&p,&w,100.f,y,265.f,1.5707963f);   // восток по оси +x
    float dt=1.f/60,t=0,t60=-1,t90=-1,airT=0,maxVy=0,maxLift=0;
    for(int i=0;i<60;i++)carUpdate(&c,&w,&(CarInput){0},dt);
    float xs=c.x,v100=0;
    for(int i=0;i<60*25&&c.x-xs<105.f;i++){CarInput in={0};in.throttle=1;carUpdate(&c,&w,&in,dt);t+=dt;
      if(t60<0&&c.v>=60/3.6f)t60=t; if(t90<0&&c.v>=90/3.6f)t90=t;
      if(c.wheels<4&&c.grounded==0)airT+=dt; if(fabsf(c.vy)>maxVy)maxVy=fabsf(c.vy); if(c.x-xs>=100.f&&!v100)v100=c.v;}
    float top=c.v;
    // торможение с макс.
    float x0=c.x,pk=0;int k=0;
    while(c.v>.3f&&k++<60*20){CarInput in={0};in.brake=1;carUpdate(&c,&w,&in,dt);if(fabsf(c.pitch)>pk)pk=fabsf(c.pitch);}
    float bt=hypotf(c.x-x0,0);
    // с 14 м/с: газом до 14, отпустить, тормоз
    Car e;carInit(&e,&p,&w,100.f,y,265.f,1.5707963f);for(int i=0;i<60;i++)carUpdate(&e,&w,&(CarInput){0},dt);
    k=0;while(e.v<14.f&&k++<60*25){CarInput in={0};in.throttle=1;carUpdate(&e,&w,&in,dt);}
    // руль: полный правый руль с газом 0.4 держим 2 с, средняя угловая скорость рыскания
    Car g=e;float h0=g.h,hh=0;
    for(int i=0;i<120;i++){CarInput in={0};in.throttle=.4f;in.steer=1;carUpdate(&g,&w,&in,dt);}
    hh=fabsf(g.h-h0)/2.f*57.2958f;
    x0=e.x;k=0;while(e.v>.3f&&k++<60*20){CarInput in={0};in.brake=1;carUpdate(&e,&w,&in,dt);}
    printf("%s\t%.0f\t%.2f\t%.2f\t%.1f\t%.1f\t%.0f\t%.2f\t%.2f\t%.2f\n",argv[a],top*3.6f,t60,t90,fabsf(e.x-x0),bt,hh,pk*57.2958f,airT,maxVy);
  }
  return 0;}
