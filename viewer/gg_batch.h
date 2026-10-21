// CPU broad phase for340; unchanged ggRisk/ggCut decide all uncertain triangles
#include "bisect.h"
#ifndef SHAR_GG_BATCH_H
#define SHAR_GG_BATCH_H
#include "ge_guard.h"
#ifndef GG_BATCH_OLD
#define GG_BATCH_OLD 0 // Director 09.10 17:05: house p95 <=11 ms; same clipping pixels
#endif
#define GG_BATCH_VERTS 48 // Port implementation policy:16 consecutive triangles, no geometry change
#define GG_BATCH_GROUPS 8 // Port policy: broad-phase hierarchy, unchanged vertex order
#define GG_BATCH_SUPER_VERTS (GG_BATCH_VERTS*GG_BATCH_GROUPS)
typedef struct { short q[6]; } GgBatch;
static inline unsigned ggBatchCount(unsigned n){return (n+GG_BATCH_VERTS-1)/GG_BATCH_VERTS;}
static inline void ggBatchBuild(GgBatch*out,const void*base,unsigned n,unsigned stride,unsigned po){
 const unsigned char*b=base;
 for(unsigned j=0;j<ggBatchCount(n);j++){
  unsigned first=j*GG_BATCH_VERTS,end=first+GG_BATCH_VERTS;if(end>n)end=n;
  const short*q=(const short*)(b+first*stride+po);
  for(int a=0;a<3;a++)out[j].q[a]=out[j].q[a+3]=q[a];
  for(unsigned i=first+1;i<end;i++){
   q=(const short*)(b+i*stride+po);
   for(int a=0;a<3;a++){if(q[a]<out[j].q[a])out[j].q[a]=q[a];if(q[a]>out[j].q[a+3])out[j].q[a+3]=q[a];}
  }
 }
}
static inline unsigned ggBatchSupers(unsigned n){return (ggBatchCount(n)+GG_BATCH_GROUPS-1)/GG_BATCH_GROUPS;}
// Broad groups, then triangle groups. Stored only for resident cells
static inline unsigned ggBatchStorage(unsigned n){return ggBatchSupers(n)+ggBatchCount(n);}
static inline void ggBatchCacheBuild(GgBatch*out,const void*base,unsigned n,unsigned stride,unsigned po){
 if(!n)return;
 GgBatch*leaf=out+ggBatchSupers(n);ggBatchBuild(leaf,base,n,stride,po);
 for(unsigned i=0;i<ggBatchCount(n);i++){
  GgBatch*p=out+i/GG_BATCH_GROUPS;
  if(i%GG_BATCH_GROUPS==0)*p=leaf[i];
  else for(int a=0;a<3;a++){
   if(leaf[i].q[a]<p->q[a])p->q[a]=leaf[i].q[a];
   if(leaf[i].q[a+3]>p->q[a+3])p->q[a+3]=leaf[i].q[a+3];
  }
 }
}
// Same order/float operations as drawGeoG: monotone products and sums bound every vertex
static inline float ggBatchBound(const GgBatch*b,const float a[3],float bias,int high){
 float x=b->q[((a[0]>=0)==high)?3:0]*(1.f/32768.f);
 float y=b->q[((a[1]>=0)==high)?4:1]*(1.f/32768.f);
 float z=b->q[((a[2]>=0)==high)?5:2]*(1.f/32768.f);
 return a[0]*x+a[1]*y+a[2]*z+bias;
}
static inline int ggBatchMayRisk(const GgBatch*b,const float a[3][3],const float bias[3],const GgCam*k){
 float zl=ggBatchBound(b,a[2],bias[2],0);
 if(zl>=GG_ZFAR)return 0;
 float zh=ggBatchBound(b,a[2],bias[2],1);
 if(zh<k->zn)return 0;
 float xl=ggBatchBound(b,a[0],bias[0],0),xh=ggBatchBound(b,a[0],bias[0],1);
 float yl=ggBatchBound(b,a[1],bias[1],0),yh=ggBatchBound(b,a[1],bias[1],1);
 if(xl>k->tvx*zh||-xh>k->tvx*zh||yl>k->tvy*zh||-yh>k->tvy*zh)return 0;
 float sx=k->tvx*(GG_SAFE/240.f),sy=k->tvy*(GG_SAFE/136.f);
 return !(zl>=k->zn*GG_NEAR&&xh<=sx*zl&&-xl<=sx*zl&&yh<=sy*zl&&-yl<=sy*zl);
}
#endif
