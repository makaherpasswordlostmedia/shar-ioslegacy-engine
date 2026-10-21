#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "col.h"
static Props props; static ColWorld W;
// у каждого тонкого пропа: твёрдые объёмы COL1 (ящик/цилиндр/сегмент забора) на расстоянии < R по xz и пересекающие высоту кузова
static float distBox(const ColBox*b,float x,float z){float dx=x-b->c[0],dz=z-b->c[2];float lx=0,lz=0;
  // проекция в xz: приблизительно по оси ax/az горизонтальной проекции
  float ax[2]={b->ax[0],b->ax[2]},az[2]={b->az[0],b->az[2]},ay[2]={b->ay[0],b->ay[2]};float best=1e9f;
  const float*A[3]={b->ax,b->ay,b->az};float dd=0;
  // расстояние до проекции ящика: SAT-приближение — внутри прямоугольника в локальных осях xz-проекции с полуразмерами
  float ex=fabsf(b->ax[0])*b->h[0]+fabsf(b->ay[0])*b->h[1]+fabsf(b->az[0])*b->h[2];float ez=fabsf(b->ax[2])*b->h[0]+fabsf(b->ay[2])*b->h[1]+fabsf(b->az[2])*b->h[2];
  float ox=fmaxf(0,fabsf(dx)-ex),oz=fmaxf(0,fabsf(dz)-ez);(void)A;(void)ax;(void)az;(void)ay;(void)lx;(void)lz;(void)dd;(void)best;return hypotf(ox,oz);}
int main(int argc,char**argv){FILE*f=fopen(argv[1],"rb");fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);unsigned char*d=malloc(n);if(fread(d,1,n,f)!=(size_t)n)return 2;fclose(f);
  unsigned co=*(unsigned*)(d+92),po=*(unsigned*)(d+96),pv=*(unsigned*)(d+88),ce=(unsigned)n;if(po>co&&po<ce)ce=po;if(pv>co&&pv<ce)ce=pv;
  if(colInit(&W,d+co,ce-co)||propsInit(&props,d+po,*(unsigned*)(d+po+40)))return 2;
  float R=argc>2?atof(argv[2]):2.5f;int thin=0,withBox=0,withCyl=0,withSeg=0,any=0;int perType[64]={0},perTypeAny[64]={0};
  for(unsigned i=0;i<props.ninst;i++){unsigned t=props.def[i].type;if(!(props.trunk&&props.trunk[t*3+2]>0))continue;thin++;perType[t]++;
    float x=props.st[i].x,z=props.st[i].z,y=props.st[i].y;int hb=0,hc=0,hs=0;
    for(unsigned k=0;k<W.nbox;k++){const ColBox*b=&W.box[k];if(b->pad>0.5f)continue;if(fabsf(b->c[1]-y)>6.f)continue;if(distBox(b,x,z)<R){hb++;}}
    for(unsigned k=0;k<W.ncyl;k++){const ColCyl*c=&W.cyl[k];if(c->pad[0]>0.5f)continue;float dx=x-c->c[0],dz=z-c->c[2];float dxz=hypotf(dx,dz);float rr=c->r+(c->halfLen*hypotf(c->axis[0],c->axis[2]));if(fabsf(c->c[1]-y)>6.f)continue;if(dxz<rr+R)hc++;}
    for(unsigned k=0;k<W.nseg;k++){const ColSeg*s=&W.seg[k];if(y+2.f<s->y0||y-1.f>s->y1)continue;float ex=s->b[0]-s->a[0],ez=s->b[1]-s->a[1],l2=ex*ex+ez*ez;float u=l2>0?((x-s->a[0])*ex+(z-s->a[1])*ez)/l2:0;u=fmaxf(0,fminf(1,u));if(hypotf(x-(s->a[0]+u*ex),z-(s->a[1]+u*ez))<R)hs++;}
    if(hb)withBox++;if(hc)withCyl++;if(hs)withSeg++;if(hb||hc||hs){any++;perTypeAny[t]++;}}
  printf("тонких экземпляров %d; с твёрдым ящиком в %.1f м: %d; цилиндром/капсулой: %d; забором: %d; любым: %d\\n",thin,R,withBox,withCyl,withSeg,any);
  for(unsigned t=0;t<props.ntype&&t<64;t++)if(perType[t])printf("  тип %u: экземпляров %d, из них с объёмом рядом %d\\n",t,perType[t],perTypeAny[t]);
  return 0;}
