// №388: удар флота о стену L1 на 10/15/20 м/с (скольжение по стене у (182.7,75.3), не лобовой). Сборка: cc -std=c11 -O2 -I viewer tools/cartest/fleet_hit_l1.c viewer/car.c viewer/col.c -lm -o fleet_hit; запуск: ./fleet_hit build/level.shr 206.4 142.1 -2.8274 famil_v bart_v ...
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "col.h"
// удар о стену L1 (448.8,-453.2, нормаль -x) на 10/15/20 м/с: скорость после, отскок, подброс, урон
int main(int argc,char **argv){
  FILE *f=fopen(argv[1],"rb");fseek(f,0,SEEK_END);unsigned n=ftell(f);rewind(f);unsigned char *b=malloc(n);
  if(fread(b,1,n,f)!=n)return 2;fclose(f);
  unsigned co=*(unsigned*)(b+92),po=*(unsigned*)(b+96),pv=*(unsigned*)(b+88),end=n;
  if(po>co&&po<end)end=po;if(pv>co&&pv<end)end=pv;
  ColWorld w;if(colInit(&w,b+co,end-co))return 2;
  float X0=atof(argv[2]),Z0=atof(argv[3]),H=atof(argv[4]);int ca=5;
  printf("car\tvt\tclosing\tv_after0.5s\tmax_rebound\tmax_vy\tdamage\n");
  for(;ca<argc;ca++){
    for(int k=0;k<3;k++){float vt=(k==0?10:k==1?15:20);
      CarParams p;carParamsFor(argv[ca],&p);float y;if(!colGround(&w,X0,Z0,10,-10,&y,0)){puts("no ground");return 3;}
      Car c;carInit(&c,&p,&w,X0,y,Z0,H);float dt=1.f/60;
      for(int i=0;i<60;i++)carUpdate(&c,&w,&(CarInput){0},dt);
      int hit=0,tAfter=-1;float closing=0,reb=0,vyMax=0,vAfter=0;
      for(int i=0;i<60*20&&!(hit&&i-tAfter>40);i++){CarInput in={0};
        if(!hit){ if(c.v<vt)in.throttle=1; }
        carUpdate(&c,&w,&in,dt);
        if(!hit&&i>30&&c.wallV>1.f){hit=1;tAfter=i;closing=c.wallV;fprintf(stderr,"hit x=%.1f z=%.1f v=%.1f\n",c.x,c.z,c.v);}
        if(hit){ if(c.v<reb)reb=c.v; if(fabsf(c.vy)>vyMax)vyMax=fabsf(c.vy); if(i-tAfter==30)vAfter=c.v; }
      }
      printf("%s\t%.0f\t%.1f\t%.1f\t%.1f\t%.2f\t%.3f\n",argv[ca],vt,closing,vAfter,reb,vyMax,c.damage);
    }
  }
  return 0;}
