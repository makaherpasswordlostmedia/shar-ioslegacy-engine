// Правка Роба 607 (15.10, L3 C7-4 причал): «жёсткая горка/кочка: шов подбрасывает машину вверх и выбивает вперёд». Решётка заездов по палубе
// причала (x -502..-462, z -62..-30, ровная палуба около -68.3): 16 курсов x смещения, 10 и 20 м/с, без газа. Событие — подскок вертикальной
// скорости на кадр больше 1,2 м/с с вертикальной скоростью выше 1,5 м/с на палубе. Шов — ступенька 0,33 м с гранью n.y 0,775 (z -55…-54,75 и
// x -485,75…-485,5). Правило car.c STEP_SEAM_OLD: опора колеса на такой ступеньке — ровная (нормаль вверх), склоны остаются склонами.
// Зелёный: событий не больше 40 % прежних, прыжок скорости вперёд за кадр на 20 м/с не выше 1,2 м/с. Красный: -DSTEP_SEAM_OLD=1.
//   step_seam_test LEVEL.shr   (L3 и L6 — одна карта причалов; код возврата = число провалов)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"
static ColWorld W;
int main(int argc,char**argv){
  FILE *f=fopen(argv[1],"rb"); fseek(f,0,SEEK_END); long size=ftell(f); rewind(f);
  unsigned char *data=malloc((size+15)&~15); fread(data,1,size,f); fclose(f);
  unsigned co=*(unsigned*)(data+92), ce=*(unsigned*)(data+96); colInit(&W,data+co,ce-co);
  int events=0, runs=0; float maxvy[2]={0,0}, maxdv[2]={0,0}; float spds[2]={10,20};
  for(int si=0;si<2;si++) for(int di=0;di<16;di++){
    float h=di*(6.2831853f/16), ux=sinf(h), uz=cosf(h);
    for(float off=-14; off<=14; off+=2){
      float cx=-483.f-uz*off, cz=-48.f+ux*off, sx=cx-ux*18, sz=cz-uz*18, g;
      if(!colGround(&W,sx,sz,-60,-80,&g,0) || fabsf(g+68.3f)>1.2f) continue;
      Car c; carInit(&c,NULL,&W,sx,g+0.6f,sz,h); carSetSpeed(&c,spds[si]); runs++;
      float pvy=0, y0=g, pv=spds[si];
      for(int st=0;st<150;st++){
        CarInput in={0.f,0,0,0}; carUpdate(&c,&W,&in,1.f/60.f);
        float along=(c.x-cx)*ux+(c.z-cz)*uz;
        if(c.y<y0-3)break;
        if(c.x<-502||c.x>-462||c.z<-62||c.z>-30) { if(along>8)break; else continue; }
        float dvy=c.vel[1]-pvy; pvy=c.vel[1]; { float vv=hypotf(c.vel[0],c.vel[2]); if(c.y<y0+2 && c.vel[1]>maxvy[si]) maxvy[si]=c.vel[1]; if(vv-pv>maxdv[si]) maxdv[si]=vv-pv; pv=vv; }
        if(dvy>1.2f && c.vel[1]>1.5f && c.y<y0+2){ printf("v%.0f h%3.0f off%+3.0f st%3d pos(%.1f %.2f %.1f) vy %.2f (+%.2f) v=%.1f contacts %d ct %d%d grounded %d wheels %d\n",spds[si],h*57.3f,off,st,c.x,c.y,c.z,c.vel[1],dvy,hypotf(c.vel[0],c.vel[2]),c.contacts,c.ctype[0],c.ctype[1],c.grounded,c.wheels); events++; break;}
      }
    }
  }
  printf("runs %d events %d | v10: max vy %.2f max dv/frame %.2f | v20: max vy %.2f max dv/frame %.2f\n",runs,events,maxvy[0],maxdv[0],maxvy[1],maxdv[1]);
  printf("%s\n", events * 2 <= 26 && maxdv[1] <= 1.2f ? "ok: шов причала не подбрасывает" : "FAIL: шов причала подбрасывает/выбивает вперёд");
  return events * 2 <= 26 && maxdv[1] <= 1.2f ? 0 : 1;}
