// Гладкий пандус 18° у гаража АЭС L1 (порт z −300…−293): у PS2 Гомер идёт по нему пешком вверх и вниз (Стенд2, ps2-npp-garage-ramp-homer.yaml).
// Красный контроль: -DHOMER_STEP=0.004f.
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
  if(argc<3)return 2;const char*lvl=argv[1],*hom=argv[2];FILE*f=fopen(lvl,"rb");unsigned char hdr[104];if(fread(hdr,1,104,f)!=104)return 2;
  unsigned pvsOff=*(unsigned*)(hdr+88),colOff=*(unsigned*)(hdr+92),propOff=*(unsigned*)(hdr+96);fseek(f,0,SEEK_END);unsigned fsize=ftell(f);
  unsigned end=fsize;if(pvsOff>colOff&&pvsOff<end)end=pvsOff;if(propOff>colOff&&propOff<end)end=propOff;
  unsigned char*cm=aligned_alloc(16,(end-colOff+15)&~15u);fseek(f,colOff,SEEK_SET);if(fread(cm,1,end-colOff,f)!=end-colOff)return 2;fclose(f);
  if(colInit(&world,cm,end-colOff))return 1;
  SkinModel*m=skinLoad(hom);static Homer H;if(homerInit(&H,m))return 1;
  float dt=1.f/60;HomerCar hc;memset(&hc,0,sizeof hc);carInit(&car,NULL,&world,-60,0,-260,0);homerCarFrom(&hc,&car,0.62f);
  // вверх: гладкий пандус 18° (z -300…-293, x -96…-87, y -3,1 → 0) пешком по +x без прыжка
  float gy;colGround(&world,-96.f,-296.f,5,-9,&gy,0);homerPlace(&H,&world,-96.f,gy+0.05f,-296.f,1.5708f);
  HomerInput in;memset(&in,0,sizeof in);in.camYaw=1.5708f;in.my=1.f;
  for(int i=0;i<60*6;i++){homerUpdate(&H,&world,&hc,&in,dt);homerPose(&H);}
  float xu=H.x,yu=H.y;
  // вниз: с верха по -x
  in.my=0.f;for(int i=0;i<30;i++){homerUpdate(&H,&world,&hc,&in,dt);homerPose(&H);}
  in.camYaw=-1.5708f;in.my=1.f;for(int i=0;i<60*6;i++){homerUpdate(&H,&world,&hc,&in,dt);homerPose(&H);}
  float xd=H.x,yd=H.y;
  int up=yu>-0.3f&&xu>-88.f,down=yd<-2.8f&&xd<-95.f;
  printf("вверх: (%.2f %.2f) %s; вниз: (%.2f %.2f) %s\n",xu,yu,up?"ok":"FAIL",xd,yd,down?"ok":"FAIL");
  printf("%s: Гомер пешком (без прыжка) идёт по гладкому пандусу 18° выезда гаража АЭС вверх и вниз\n",up&&down?"OK":"FAIL");return up&&down?0:1;}
