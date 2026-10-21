#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "gg_batch.h"
typedef struct {float a[3][3],b[3];GgCam k;uint32_t n,stride,po;} Input;
int main(int argc,char**argv){
 if(argc!=2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;
 uint32_t nr;if(fread(&nr,4,1,f)!=1)return 2;
 unsigned long long all=0,exam=0,risky=0,miss=0;
 for(unsigned r=0;r<nr;r++){
  Input h;if(fread(&h,sizeof h,1,f)!=1||!h.n||h.n%3||h.n>65535||h.stride>16)return 2;
  unsigned char*raw=malloc(h.n*h.stride);GgBatch*groups=malloc(ggBatchStorage(h.n)*sizeof *groups);
  if(!raw||!groups||fread(raw,h.n*h.stride,1,f)!=1)return 2;
  ggBatchCacheBuild(groups,raw,h.n,h.stride,h.po);
  for(unsigned t=0;t<h.n;t+=3){
   GgV v[3]={0};for(int i=0;i<3;i++){
    const short*q=(const short*)(raw+(t+i)*h.stride+h.po);
    for(int j=0;j<3;j++)v[i].l[j]=q[j]*(1.f/32768.f);
    for(int j=0;j<3;j++)v[i].c[j]=h.a[j][0]*v[i].l[0]+h.a[j][1]*v[i].l[1]+h.a[j][2]*v[i].l[2]+h.b[j];
   }
#ifdef GG_BATCH_TEST_SHRINK
   GgBatch bad=groups[ggBatchSupers(h.n)+t/GG_BATCH_VERTS];for(int j=0;j<3;j++)bad.q[j]=bad.q[j+3]=(bad.q[j]+bad.q[j+3])/2;
   int scan=ggBatchMayRisk(&bad,h.a,h.b,&h.k);
#else
   int scan=GG_BATCH_OLD||(ggBatchMayRisk(groups+t/GG_BATCH_SUPER_VERTS,h.a,h.b,&h.k)&&ggBatchMayRisk(&groups[ggBatchSupers(h.n)+t/GG_BATCH_VERTS],h.a,h.b,&h.k));
#endif
   int old=ggRisk(v,v+1,v+2,&h.k);int now=scan?ggRisk(v,v+1,v+2,&h.k):0;
   all++;exam+=scan;risky+=old;miss+=old!=now;
  }
  free(raw);free(groups);
 }
 fclose(f);printf("all=%llu exam=%llu risky=%llu missed=%llu\n",all,exam,risky,miss);
 return miss||!risky||exam>=all?1:0;
}
