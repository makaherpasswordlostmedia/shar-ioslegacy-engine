#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "car.h"
#include "col.h"
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fl;
int main(int argc,char**argv){memset(&fl,0,sizeof fl);memcpy(fl.h.magic,"COL1",4);fl.h.ox=fl.h.oz=-2000;fl.h.cell=4000;fl.h.W=fl.h.H=1;fl.h.ntri=fl.h.nref=2;
fl.t[0]=(ColTri){{-2000,0,-2000},{2000,0,2000},{2000,0,-2000},{0,1,0}};fl.t[1]=(ColTri){{-2000,0,-2000},{-2000,0,2000},{2000,0,2000},{0,1,0}};fl.start[1]=2;fl.refs[0]=0;fl.refs[1]=1;
ColWorld w;if(colInit(&w,&fl,sizeof fl))return 2;
float dt=1.f/50;
for(int a=2;a<argc;a++){CarParams p;carParamsFor(argv[a],&p);float y;y=0;
 // торможение с 14.4
 Car c;carInit(&c,&p,&w,0.f,y,0.f,1.5707963f);for(int i=0;i<50;i++)carUpdate(&c,&w,&(CarInput){0},dt);
 int k=0;while(c.v<14.4f&&k++<3000){CarInput in={0};in.throttle=1;carUpdate(&c,&w,&in,dt);}
 float x0=c.x,z0=c.z;int fr=0;float pk=0;while(c.v>0.15f&&fr<600){CarInput in={0};in.brake=1;carUpdate(&c,&w,&in,dt);fr++;if(fabsf(c.pitch)>pk)pk=fabsf(c.pitch);}
 printf("%s: тормоз 14,4 м/с: %.2f с (%d кадров), путь %.1f м, макс тангаж %.2f°\\n",argv[a],fr/50.f,fr,hypotf(c.x-x0,c.z-z0),pk*57.3f);
 // руль: до 14.3 затем газ держит 14, руль влево 3 с и вправо 3 с
 for(int side=-1;side<=1;side+=2){Car d;carInit(&d,&p,&w,0.f,y,0.f,1.5707963f);for(int i=0;i<50;i++)carUpdate(&d,&w,&(CarInput){0},dt);
  k=0;while(d.v<14.3f&&k++<3000){CarInput in={0};in.throttle=1;carUpdate(&d,&w,&in,dt);}
  float h0=d.h,hmax=0,rmax=0,prev=d.h,sum=0;for(int i=0;i<150;i++){CarInput in={0};in.steer=side;in.throttle=d.v<14.3f?1.f:0.f;carUpdate(&d,&w,&in,dt);float dh=d.h-prev;while(dh>3.14159f)dh-=6.28318f;while(dh<-3.14159f)dh+=6.28318f;prev=d.h;sum+=fabsf(dh);if(fabsf(dh)*50*57.3f>hmax)hmax=fabsf(dh)*50*57.3f;if(fabsf(d.roll)>rmax)rmax=fabsf(d.roll);}
  float dtot=d.h-h0;while(dtot>3.14159f)dtot-=6.28318f;while(dtot<-3.14159f)dtot+=6.28318f;
  printf("   руль %s: средняя рыскание ~%.0f°/с (за 3 с %.0f°), макс %.0f°/с, крен до %.1f°, v в конце %.1f\\n",side<0?"влево":"вправо",sum*57.3f/3.f,sum*57.3f,hmax,rmax*57.3f,d.v);}
}
return 0;}
