// №488: наезд на тонкие стоячие пропы (фонарь/знак/гидрант): зазор до ствола, сбитие, потеря скорости. cc -std=c11 -O2 -DSKIN_HOST -I viewer tools/cartest/prop_thin_hit.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c viewer/homer.c viewer/skin.c -lm; ./a.out LEVEL.shr X Z DX DZ (TL=1 V1=1 — трасса скорости)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"
static PropState *saved; static Props props; static ColWorld W; static Car car;
// наезд на тонкие пропы (фонарь, знак, гидрант): зазор до ствола при первом контакте, сбивается ли, потеря скорости
static int run(unsigned i,float dirx,float dirz,float v,float *gap,int *kicked,float *loss,float *vend,int *wall){
  PropDef*pd=&props.def[i];PropType*ty=&props.types[pd->type];float tx=pd->x,tz=pd->z,tr=0;
  if(props.trunk&&props.trunk[pd->type*3+2]>0){ // центр ствола в осях модели -> мир (пренебрегаем поворотом модели: без него q=ident у стоячих)
    tx=pd->x+props.trunk[pd->type*3];tz=pd->z+props.trunk[pd->type*3+1];tr=props.trunk[pd->type*3+2];}
  float sx=tx-dirx*16.f,sz=tz-dirz*16.f,g;if(!colGround(&W,sx,sz,pd->y+4.f,pd->y-6.f,&g,0))return 0;
  carInit(&car,NULL,&W,sx,g+0.3f,sz,atan2f(dirx,dirz));for(int k=0;k<30;k++){CarInput in={0};carUpdate(&car,&W,&in,1/60.f);}
  carSetSpeed(&car,v);props.havePreviousCar=0;
  memcpy(props.st,saved,props.ninst*sizeof(PropState));
  PropState*st=&props.st[i];*kicked=0;*gap=99;*wall=0;float vc0=v;int tk=-1;
  for(int fr=0;fr<6*60;fr++){CarInput in={0};float vb=hypotf(car.vel[0],car.vel[2]);in.throttle=(tk<0&&vb<v)?1.f:0.f;
    carUpdate(&car,&W,&in,1/60.f);propsUpdate(&props,&W,&car,1/60.f);
    if(car.contacts>0&&tk<0)*wall=1;
    if(tk<0&&(!st->asleep||st->hidden)){tk=fr;*kicked=1;vc0=vb;CarBox b;carBox(&car,&b);float along=(tx-b.x)*dirx+(tz-b.z)*dirz;*gap=along-b.hl-tr;}
    if(tk>=0&&fr-tk==18){*loss=vc0-hypotf(car.vel[0],car.vel[2]);}
    if(getenv("TL")&&(tk<0?fr%10==0&&fr>=60:(fr-tk)%6==0&&fr-tk<=36))fprintf(stderr,"   %s fr=%d pos(%.2f,%.2f) v=%.2f contacts=%d ct=%d%d%d hitSpeed=%.1f crashes=%d wallV=%.1f\n",tk<0?"до":"после",fr,car.x,car.z,hypotf(car.vel[0],car.vel[2]),car.contacts,car.ctype[0],car.ctype[1],car.ctype[2],car.hitSpeed,car.crashes,car.wallV);
    if(tk<0&&hypotf(car.vel[0],car.vel[2])<0.4f&&fr>60){*gap=-98;break;}
  }
  *vend=hypotf(car.vel[0],car.vel[2]);if(!*kicked&&*gap>90)*gap=-97;return 1;}
int main(int argc,char**argv){
  FILE*f=fopen(argv[1],"rb");fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char*d=malloc(n);if(fread(d,1,n,f)!=(size_t)n)return 2;fclose(f);
  unsigned co=*(unsigned*)(d+92),po=*(unsigned*)(d+96),pv=*(unsigned*)(d+88),ce=(unsigned)n;if(po>co&&po<ce)ce=po;if(pv>co&&pv<ce)ce=pv;
  if(colInit(&W,d+co,ce-co)||propsInit(&props,d+po,*(unsigned*)(d+po+40)))return 2;
  saved=malloc(props.ninst*sizeof(PropState));memcpy(saved,props.st,props.ninst*sizeof(PropState));
float qx=atof(argv[2]),qz=atof(argv[3]),dx=atof(argv[4]),dz=atof(argv[5]);float l=hypotf(dx,dz);dx/=l;dz/=l;
for(unsigned i=0;i<props.ninst;i++){float d=hypotf(props.def[i].x-qx,props.def[i].z-qz);if(d<8.f){PropType*ty=&props.types[props.def[i].type];printf("проп %u тип %u в (%.1f %.1f) d=%.1f radius %.2f halfH %.2f масса %.0f ствол r %.2f\\n",i,props.def[i].type,props.def[i].x,props.def[i].z,d,ty->radius,ty->halfH,ty->mass,props.trunk&&props.trunk[props.def[i].type*3+2]>0?props.trunk[props.def[i].type*3+2]:0.f);
 for(int vi=0;vi<3;vi++){float v=vi==0?5.f:vi==1?8.4f:14.f;if(getenv("V1")&&vi!=1)continue;float gap=0,loss=0,vend=0;int k=0,w=0;run(i,dx,dz,v,&gap,&k,&loss,&vend,&w);printf("   v=%.1f gap=%.2f сбит=%d потеря за 0,3 с=%.2f стена=%d\\n",v,gap,k,loss,w);}}}
return 0;}
