// 391: actual FXP1 ring/stain quads must be tangent to the road normal, on all levels.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <string.h>
#include "fxdsp.h"
static unsigned u32(const unsigned char *p) { unsigned v; memcpy(&v,p,4); return v; }
int main(int argc,char **argv) {
  if(argc<2)return 2;
  FILE *f=fopen(argv[1],"rb");if(!f)return 2;
  fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);
  unsigned char *data=malloc(size);if(fread(data,1,size,f)!=(size_t)size)return 2;fclose(f);
  unsigned nbb=u32(data+24),offbb=u32(data+52),nbr=u32(data+32),offbr=u32(data+60);
  FxBB *bb=calloc(nbb,sizeof *bb);memcpy(bb,data+offbb,nbb*sizeof *bb);
  int first=-1,count=0;
  for(unsigned i=0;i<nbr;i++){const unsigned short *b=(const unsigned short *)(data+offbr+16*i);if(b[0]==24){first=b[6];count=b[7];}}
  if(first<0)return 2;
  int checked=0,bad=0;
  for(int i=first;i<first+count;i++){
    if(bb[i].mode!=0)continue;
    bb[i].mode=2;
    for(int slope=0;slope<3;slope++){
      FxJob *j=calloc(1,sizeof *j);FxV verts[4];
      j->BB=bb;j->E=(const FxEmit *)(data+u32(data+44));j->blob=data;j->vout=verts;
      j->stage=FXD_BUILD|(argc>2?FXD_GROUND_OLD:0);j->nt=u32(data+8);j->nb=1;j->fillK=1;
      j->ex=30;j->ey=15;j->ez=30;j->fx=-.6666667f;j->fy=-.3333333f;j->fz=-.6666667f;
      j->bb[0].bb=i;j->bb[0].t=10;
      float *n=j->bb[0].up;n[0]=slope==1?.3f:0;n[1]=1;n[2]=slope==2?-.4f:0;
      float len=sqrtf(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);for(int k=0;k<3;k++)n[k]/=len;
      fxdRun(j);checked++;
      float err=0;
      if(j->nq!=1)err=999;
      else for(int k=0;k<4;k++){
        float d=(verts[k].x-verts[0].x)*n[0]+(verts[k].y-verts[0].y)*n[1]+(verts[k].z-verts[0].z)*n[2];
        if(fabsf(d)>err)err=fabsf(d);
      }
      if(err>1e-4f){bad++;printf("FAIL billboard%d slope%d plane_error%.4f\n",i,slope,err);}
      free(j);
    }
  }
  printf("quads=%d failures=%d\n",checked,bad);free(bb);free(data);
  return bad||checked<6?1:0;
}
