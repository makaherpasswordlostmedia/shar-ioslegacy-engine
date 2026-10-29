// Runtime split of the unchanged CLT1 file. Only dense SPR1 keys and CHR1
// blobs are detached; all logic/visibility/collision and card/wasp data remain.
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "coll_stream.h"
#ifndef SKIN_HOST
#include <malloc.h>
#include <pspkernel.h>
#endif
int gagSkinStreamOld=GAG_SKIN_STREAM_OLD;
unsigned collStreamResidentBytes,collStreamTrackBytes;
static CollectRead source;static void *sourceUser;
static unsigned keyOffset;
static float **keys;static unsigned ntypes;
static int *typeGag;static const StateProps *liveSp;
#define A16(x) (((x)+15u)&~15u)
static void *aligned(unsigned n) {
#ifdef SKIN_HOST
  return aligned_alloc(16,A16(n));
#else
  return memalign(16,n);
#endif
}
void collStreamFree(void) {
  if(keys)for(unsigned i=0;i<ntypes;i++)free(keys[i]);
  free(keys);free(typeGag);keys=0;typeGag=0;ntypes=0;source=0;sourceUser=0;liveSp=0;
  collStreamResidentBytes=collStreamTrackBytes=0;
}
static int loadKeys(const StateProps *sp,unsigned i) {
  const SpType *t=sp->type+i;
  unsigned bytes=(unsigned)(t->frames&65535u)*(t->frames>>16)*28u;
  if(!bytes || keys[i])return 0;
  keys[i]=aligned(bytes);if(!keys[i])return -1;
  if(source(sourceUser,keyOffset+t->keyOff*28u,keys[i],bytes)){free(keys[i]);keys[i]=0;return -1;}
  collStreamTrackBytes+=bytes;return 0;
}
static int ensureKey(unsigned i){return liveSp && i<ntypes ? loadKeys(liveSp,i) : -1;}
void *collStreamLoad(Collect *c,CollectRead read,void *user,unsigned size) {
  collStreamFree();
  unsigned h[20],s[16];
  if(size<80 || read(user,0,h,80) || memcmp(h,"CLT1",4) || h[1]<3 || h[5]>size-64 || read(user,h[5],s,64) || memcmp(s,"SPR1",4))return 0;
  if(h[6]>size-h[5] || h[14]>size/64u || s[12]>size || s[13]>size ||
      s[1]>size/84u || s[3]>size/40u || s[4]>size/52u || s[5]>size/28u)return 0;
  uint64_t off=(uint64_t)h[5]+64+A16(s[12])+A16(s[13])+A16(s[3]*40u)+A16(s[1]*84u)+A16(s[4]*52u);
  uint64_t keyBytes=(uint64_t)s[5]*28u;keyBytes=(keyBytes+15u)&~15ull;
  uint64_t end=(uint64_t)h[15]+(uint64_t)h[14]*64u;
  if(off+keyBytes>size || end>size || end<off+keyBytes || keyBytes>h[6] || (off&15) || (h[15]&15))return 0;
  unsigned n=(unsigned)(end-keyBytes),kb=(unsigned)keyBytes;
  unsigned char *b=aligned(n);if(!b)return 0;
  if(read(user,0,b,(unsigned)off) || read(user,(unsigned)(off+keyBytes),b+off,(unsigned)(end-off-keyBytes))){free(b);return 0;}
  unsigned *u=(unsigned *)b;
  u[6]-=kb;u[8]-=kb;u[10]-=kb;u[12]-=kb;u[15]-=kb;
  if(collectInitResident(c,b,n,1)){free(b);return 0;}
  source=read;sourceUser=user;keyOffset=(unsigned)off;ntypes=c->sp.ntype;
  keys=calloc(ntypes,sizeof *keys);typeGag=malloc(ntypes*sizeof *typeGag);
  if(!keys || !typeGag)goto bad;
  for(unsigned i=0;i<ntypes;i++)typeGag[i]=-1;
  for(unsigned g=0;g<c->ngag;g++)if(c->gag[g].inst>=0)typeGag[c->sp.inst[c->gag[g].inst].type]=(int)g;
  c->sp.typeKey=(const float *const *)keys;c->sp.ensureKey=ensureKey;liveSp=&c->sp;
  for(unsigned i=0;i<ntypes;i++)if(typeGag[i]<0 && loadKeys(&c->sp,i))goto bad;
  if(gagSkinInitSource(c,read,user,size)<0)goto bad;
  collStreamResidentBytes=n;return b;
bad:gagSkinFree();collectFree(c);collStreamFree();free(b);return 0;
}
int collStreamPrepare(Collect *c,int room,float ex,float ez,float distance,int snap) {
  if(!source)return 0;
  unsigned char wanted[COLL_MAXGAG]={0};
  for(unsigned g=0;g<c->ngag;g++){
    const CollGag *a=c->gag+g;float dx=a->x-ex,dz=a->z-ez;
    // Same draw set, with a 10 metre prefetch margin (port I/O policy).
    wanted[g]=a->room==room && (!a->random || (snap>=0 ? (int)g==snap : c->st.gagPick[g])) &&
        dx*dx+dz*dz<=(distance+10.f)*(distance+10.f);
  }
  for(unsigned i=0;i<ntypes;i++)if(typeGag[i]>=0 && !wanted[typeGag[i]] && keys[i]){
    const SpType *t=c->sp.type+i;collStreamTrackBytes-=(t->frames&65535u)*(t->frames>>16)*28u;
    free(keys[i]);keys[i]=0;
    for(unsigned j=0;j<c->sp.ninst;j++)if(c->sp.inst[j].type==i)c->sp.run[j].poseValid=0;
  }
  for(unsigned i=0;i<ntypes;i++)if(typeGag[i]>=0 && wanted[typeGag[i]] && loadKeys(&c->sp,i))return -1;
  return gagSkinPrepare(c,wanted);
}
