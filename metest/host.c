#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include "workloads.h"
extern void previousMix(void *),previousPoint(const int*,const int*,const void*,int*,int*);
static MixJob a,b;static SpatialJob sp;static FxJob fx,fxCopy;
static FxEmit emit __attribute__((aligned(64)));static FxV v[FX_NEL*4],vCopy[FX_NEL*4];
static unsigned char bank[16*32];
int main(int argc,char**argv){
  int red=argc>1,fail=0,checks=0;short hist[4]={0};
  for(int i=0;i<32;i++){bank[i*16]=0x0a;for(int j=2;j<16;j++)bank[i*16+j]=(unsigned char)(i+j*29);}
  const int counts[]={1,8,24,128};
  for(int q=0;q<4;q++)for(unsigned k=0;k<64;k++){
    spatialInput(&sp,counts[q],k+17);mixSpatialBatchRun(&sp);
    if(red)sp.gain[0][0]^=1;
    for(int i=0;i<sp.count;i++) {int l=32768,r=32768;previousPoint(sp.listener,sp.right,&sp.point[i],&l,&r);fail+=l!=sp.gain[i][0]||r!=sp.gain[i][1];checks++;}
  }
  for(int n=1;n<=24;n++)for(unsigned k=0;k<64;k++){
    mixerInput(&a,bank,896,0,896,24000,1,hist,n,k+13);b=a;mixDspRun(&a);previousMix(&b);
    if(red)a.acc[0]^=1;fail+=memcmp(&a,&b,sizeof a)!=0;checks++;
    // Decoder state persists through loops and changing listener, not only fresh buffers
    for(int frame=0;frame<5;frame++){a.listener[0]=b.listener[0]=frame*64;a.listener[2]=b.listener[2]=frame*160;mixDspRun(&a);previousMix(&b);fail+=memcmp(&a,&b,sizeof a)!=0;checks++;}
  }
  const int nums[]={32,128,400};
  for(int q=0;q<3;q++)for(unsigned k=0;k<64;k++){
    memset(v,0,sizeof v);memset(vCopy,0,sizeof vCopy);
    particlesInput(&fx,&emit,v,nums[q],k+3,0);fxCopy=fx;fxCopy.vout=vCopy;fxdRun(&fx);fxdRun(&fxCopy);fxCopy.vout=v;
    if(red)v[0].x+=1;fail+=memcmp(&fx,&fxCopy,sizeof fx)!=0||fx.nq<1||memcmp(v,vCopy,fx.nq*4*sizeof(FxV))!=0;checks++;
  }
  printf("%s checks=%d failures=%d negative=%d spatial-size=%zu mix-size=%zu fx-size=%zu\n",fail?"FAIL":"PASS",checks,fail,red,sizeof sp,sizeof a,sizeof fx);
  return fail?1:0;
}
