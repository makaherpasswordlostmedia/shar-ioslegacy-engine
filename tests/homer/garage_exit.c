// Гараж АЭС L1: выезд — лесенка из наклонных плит с уступами 1–1,55 м (COL1 box 1355 и соседние). Гомер пешком идёт вниз и обратно вверх
// без прыжка; зелёный (-DHOMER_STAIR_UP=1): выходит на дорогу (y 0); красный (по умолчанию без правила): встаёт у первого уступа.
//   tests/homer/garage_exit.sh [level.shr] [homer.shr]     аргументы старта: -84 0.2 -292.24 курс −1,5708 (на -x)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "homer.h"
static ColWorld world; static Car car;
int main(int argc,char**argv){
  if(argc<3)return 2;const char*lvl=argv[1],*hom=argv[2];FILE*f=fopen(lvl,"rb");unsigned char hdr[104];fread(hdr,1,104,f);
  unsigned pvsOff=*(unsigned*)(hdr+88),colOff=*(unsigned*)(hdr+92),propOff=*(unsigned*)(hdr+96);fseek(f,0,SEEK_END);unsigned fsize=ftell(f);
  unsigned end=fsize;if(pvsOff>colOff&&pvsOff<end)end=pvsOff;if(propOff>colOff&&propOff<end)end=propOff;
  unsigned char*cm=aligned_alloc(16,(end-colOff+15)&~15u);fseek(f,colOff,SEEK_SET);fread(cm,1,end-colOff,f);fclose(f);
  if(colInit(&world,cm,end-colOff))return 1;
  SkinModel*m=skinLoad(hom);static Homer H;if(homerInit(&H,m))return 1;
  float x0=-84.f,y0=0.2f,z0=-292.24f,hd=-1.5708f;   // старт и курс вниз
  float dt=1.f/60;HomerCar hc;memset(&hc,0,sizeof hc);
  carInit(&car,NULL,&world,x0+30,y0,z0+30,0);homerCarFrom(&hc,&car,0.62f);
  homerPlace(&H,&world,x0,y0,z0,hd);
  HomerInput in;memset(&in,0,sizeof in);in.camYaw=hd;in.my=1.f;
  printf("вниз:\n");for(int i=0;i<60*8;i++){homerUpdate(&H,&world,&hc,&in,dt);homerPose(&H);if(i%30==0)printf("  t=%.1f pos(%.2f %.2f %.2f) v=%.2f grounded=%d\n",i*dt,H.x,H.y,H.z,H.speed,H.grounded);}
  float xb=H.x,yb=H.y,zb=H.z;
  in.my=0.f;for(int i=0;i<30;i++){homerUpdate(&H,&world,&hc,&in,dt);homerPose(&H);}
  in.camYaw=hd+3.14159f;in.my=1.f;printf("вверх:\n");
  for(int i=0;i<60*8;i++){homerUpdate(&H,&world,&hc,&in,dt);homerPose(&H);if(i%30==0)printf("  t=%.1f pos(%.2f %.2f %.2f) v=%.2f grounded=%d\n",i*dt,H.x,H.y,H.z,H.speed,H.grounded);}
  printf("итог: низ (%.2f %.2f %.2f) → после подъёма (%.2f %.2f %.2f), встал на уступ %d раз\n",xb,yb,zb,H.x,H.y,H.z,H.stairUps);
  int ok=H.y>-0.1f&&H.x>-84.f&&yb<-7.f;
  printf("%s: Гомер пешком (без прыжка) проходит выезд гаража АЭС L1 в обе стороны\n",ok?"OK":"FAIL");return ok?0:1;}
