#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <assert.h>
#include "coll_stream.h"
static unsigned char *raw;static unsigned size,reads;
static int get(void *u,unsigned off,void *p,unsigned n){(void)u;if(off>size || n>size-off)return -1;memcpy(p,raw+off,n);reads++;return 0;}
int main(int ac,char **av){
  FILE*f=fopen(av[1],"rb");assert(f);fseek(f,0,SEEK_END);size=ftell(f);rewind(f);raw=aligned_alloc(16,(size+15u)&~15u);assert(fread(raw,1,size,f)==size);fclose(f);
  Collect old,now;assert(!collectInit(&old,raw,size));
  if(ac>2){assert(gagSkinInit(&old)>=0);printf("OLD resident=%u\n",size);gagSkinFree();collectFree(&old);free(raw);return 0;}
  void *pak=collStreamLoad(&now,get,0,size);assert(pak);
  assert(old.ngag==now.ngag && old.ncard==now.ncard && old.nwasp==now.nwasp);
  assert(!memcmp(old.gag,now.gag,old.ngag*sizeof *old.gag));assert(!memcmp(old.card,now.card,old.ncard*sizeof *old.card));assert(!memcmp(old.wasp,now.wasp,old.nwasp*sizeof *old.wasp));
  // Bind the authored EFX names as the renderer does. The fallback preset path
  // has one process-global RNG and two sequential simulations do not share it.
  for(unsigned k=0;k<spFxNameCount(&old.sp);k++){
    spFxBind(&old.sp,k,(int)k);spFxBind(&now.sp,k,(int)k);
  }
  unsigned poses=0,peak=0,skins=0;
  for(unsigned g=0;g<old.ngag;g++){
    const CollGag *a=old.gag+g;for(unsigned k=0;k<old.ngag;k++)old.st.gagPick[k]=now.st.gagPick[k]=k==g;
    assert(!collStreamPrepare(&now,a->room,a->x,a->z,80,(int)g));
    unsigned mem=collStreamResidentBytes+collStreamTrackBytes+gagSkinResidentBytes;if(mem>peak)peak=mem;
    unsigned n=gagSkinDraw(&now,a->room,a->x,a->z,80);skins+=n;
    if(a->inst<0)continue;
    unsigned inst=a->inst;const SpType *t=old.sp.type+old.sp.inst[inst].type;
    for(unsigned frame=0;frame<5;frame++){
      old.sp.run[inst].poseValid=now.sp.run[inst].poseValid=0;old.sp.run[inst].poseF=now.sp.run[inst].poseF=(t->frames&65535u)*frame/5.f;
      spPose(&old.sp,inst);spPose(&now.sp,inst);
      assert(!memcmp(old.sp.run[inst].jm,now.sp.run[inst].jm,t->nJoint*12*sizeof(float)));poses++;
    }
    unsigned before=reads;assert(!collStreamPrepare(&now,a->room,a->x,a->z,80,(int)g));assert(reads==before);
    // Exercise actual trigger/state/EFX logic, including a first pose requested
    // by logic rather than by the renderer. Both clocks and event queues agree.
    CollPlayer p={a->tx,a->ty,a->tz,1,a->room,1};
    for(unsigned tick=0;tick<40;tick++){
      collectStep(&old,&p,0,0,0,0,1.f/30.f);
      collectStep(&now,&p,0,0,0,0,1.f/30.f);
      assert(!memcmp(&old.st,&now.st,sizeof old.st));
      assert(old.sp.nfx==now.sp.nfx);
      assert(!memcmp(old.sp.fxq,now.sp.fxq,old.sp.nfx*sizeof *old.sp.fxq));
      old.sp.nfx=now.sp.nfx=0;
    }
  }
  assert(!collStreamPrepare(&now,now.gag[0].room,10000,10000,0,-1));assert(!gagSkinResidentBytes);
  for(unsigned g=0;g<now.ngag;g++)if(now.gag[g].inst>=0)assert(!now.sp.typeKey[now.sp.inst[now.gag[g].inst].type]);
  for(unsigned i=0;i<now.sp.ninst;i++)if(collectGagOf(&now,i)<0){const SpType*t=old.sp.type+old.sp.inst[i].type;old.sp.run[i].poseValid=now.sp.run[i].poseValid=0;old.sp.run[i].poseF=now.sp.run[i].poseF=1.25f;spPose(&old.sp,i);spPose(&now.sp,i);assert(!memcmp(old.sp.run[i].jm,now.sp.run[i].jm,t->nJoint*12*sizeof(float)));}
  printf("PASS L%d poses=%u skins=%u resident=%u peak=%u old=%u reads=%u\n",old.level,poses,skins,collStreamResidentBytes,peak,size,reads);
  gagSkinFree();collectFree(&old);collectFree(&now);collStreamFree();free(pak);free(raw);return 0;
}
