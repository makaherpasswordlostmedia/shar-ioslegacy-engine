#include "../../viewer/props.h"
#include "../../viewer/stateprops.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static int kicks;
static int hit(void *u,unsigned i,float x,float z){(void)u;(void)i;(void)x;(void)z;kicks++;return 1;}
static Car at(const Car *base,const PropState *s,float nx,float nz,float distance){
  Car c=*base;c.x=s->x+nx*distance;c.y=s->y;c.z=s->z+nz*distance;c.h=atan2f(nx,nz);
  c.q[0]=cosf(c.h*.5f);c.q[1]=c.q[3]=0;c.q[2]=sinf(c.h*.5f);
  CarBox b;carBox(&c,&b);c.x+=s->x+nx*distance-b.x;c.z+=s->z+nz*distance-b.z;c.y+=s->y-(b.y+.5f*(b.lo+b.hi));
  c.vel[0]=nx*30;c.vel[1]=0;c.vel[2]=nz*30;c.v=30;return c;
}
int main(int argc,char **argv){
  if(argc!=2)return 2;FILE *f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
  unsigned char *data=malloc((size_t)n);if(!data||fread(data,1,(size_t)n,f)!=(size_t)n)return 2;fclose(f);
  unsigned co=*(unsigned*)(data+92),po=*(unsigned*)(data+96);ColWorld w;Props p;StateProps sp;
  if(colInit(&w,data+co,po-co)||propsInit(&p,data+po,*(unsigned*)(data+po+40))||spInit(&sp,p.spr,p.sprSize))return 2;
  unsigned target=0;int found=0;for(unsigned i=0;i<p.ninst;i++){int pa,br;propsTypeFx(&p,p.def[i].type,&pa,&br);if(br==19){target=i;found=1;break;}}
  if(!found)return 1;PropState original=p.st[target];p.onKick=hit;
  float nx=2*(original.q[1]*original.q[3]+original.q[0]*original.q[2]),nz=1-2*(original.q[1]*original.q[1]+original.q[2]*original.q[2]);float l=hypotf(nx,nz);nx/=l;nz/=l;
  Car base;carInit(&base,0,&w,0,0,0,0);Car a=at(&base,&original,nx,nz,-4),b=at(&base,&original,nx,nz,4);CarBox pa,pb;carBox(&a,&pa);carBox(&b,&pb);
  propsHitCar(&p,&w,&a,&pa);propsHitCar(&p,&w,&b,&pb);
  if(kicks||p.st[target].hidden){puts("FAIL separate cars fabricated a glass sweep");return 1;}
  propsHitCar(&p,&w,&b,&pa);if(!p.st[target].hidden){puts("FAIL actual swept contact missed glass");return 1;}
  p.st[target]=original;p.st[target].hitCool=.5f;propsAdvance(&p,&w,.01f);float cool=p.st[target].hitCool;
  Car far=base;far.x=far.z=10000;far.vel[0]=20;carBox(&far,&pa);
  spUpdate(&sp,&w,0,0,.01f);float *times=malloc(sp.ninst*sizeof(float));for(unsigned i=0;i<sp.ninst;i++)times[i]=sp.run[i].t;
  for(int i=0;i<1024;i++){propsHitCar(&p,&w,&far,&pa);spHitCar(&sp,&w,&far,0);}
  if(fabsf(cool-.49f)>.0001f||p.st[target].hitCool!=cool){puts("FAIL prop time multiplied by actor count");return 1;}
  for(unsigned i=0;i<sp.ninst;i++)if(sp.run[i].t!=times[i]){puts("FAIL state time multiplied by actor count");return 1;}
  puts("PASS independent sweeps, actual glass break, 1024 contacts do not advance object clocks");
  free(times);propsFree(&p);spFree(&sp);colFree(&w);free(data);return 0;
}
