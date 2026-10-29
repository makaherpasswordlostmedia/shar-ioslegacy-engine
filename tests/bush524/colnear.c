#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include "col.h"
static ColWorld W;
int main(int argc,char**argv){ FILE*f=fopen(argv[1],"rb"); fseek(f,0,SEEK_END); long n=ftell(f); rewind(f); unsigned char*d=aligned_alloc(16,(n+15)&~15L); fread(d,1,n,f); fclose(f);
  uint32_t pv=*(uint32_t*)(d+88),co=*(uint32_t*)(d+92),po=*(uint32_t*)(d+96),end=n; if(po>co&&po<end)end=po; if(pv>co&&pv<end)end=pv;
  colInit(&W,d+co,end-co); float x=atof(argv[2]),z=atof(argv[3]),r=atof(argv[4]);
  for(uint32_t i=0;i<W.nbox;i++){const ColBox*b=&W.box[i]; float ex=fabsf(b->ax[0])*b->h[0]+fabsf(b->ay[0])*b->h[1]+fabsf(b->az[0])*b->h[2], ez=fabsf(b->ax[2])*b->h[0]+fabsf(b->ay[2])*b->h[1]+fabsf(b->az[2])*b->h[2];
    if(fabsf(b->c[0]-x)<r+ex && fabsf(b->c[2]-z)<r+ez) printf("box %u c=(%.1f,%.1f,%.1f) h=(%.1f,%.1f,%.1f) mat=%g\n",i,b->c[0],b->c[1],b->c[2],b->h[0],b->h[1],b->h[2],b->pad);}
  for(uint32_t i=0;i<W.ncyl;i++){const ColCyl*q=&W.cyl[i]; if(hypotf(q->c[0]-x,q->c[2]-z)<r+q->r+q->halfLen) printf("cyl %u c=(%.1f,%.1f,%.1f) axis=(%.1f,%.1f,%.1f) r=%.2f hl=%.2f mat=%g flat=%u\n",i,q->c[0],q->c[1],q->c[2],q->axis[0],q->axis[1],q->axis[2],q->r,q->halfLen,q->pad[0],q->flat);}
  for(uint32_t i=0;i<W.nseg;i++){const ColSeg*q=&W.seg[i]; float mx=(q->a[0]+q->b[0])/2,mz=(q->a[1]+q->b[1])/2, L=hypotf(q->b[0]-q->a[0],q->b[1]-q->a[1]); if(hypotf(mx-x,mz-z)<r+L/2) printf("seg %u a=(%.1f,%.1f) b=(%.1f,%.1f) y=%.1f..%.1f len %.1f\n",i,q->a[0],q->a[1],q->b[0],q->b[1],q->y0,q->y1,L);}
  return 0;}
