#include <stdio.h>
#include <math.h>
#include "skid.h"
#include "../../viewer/audio.c"
static int bad,starts;
static void note(int id,const char *why){(void)id;if(!strcmp(why,"skid"))starts++;}
int main(int argc,char**argv){if(argc!=2||audioInit(argv[1]))return 2;audioNote=note;
 const SabCar*profiles=(const SabCar*)(bank+H->carOff);int audible=0,silent=0;
 for(unsigned j=0;j<H->ncar;j++){
  const char*name=profiles[j].name;Car c={0};carParamsFor(name,&c.p);c.q[0]=1;c.grounded=1;c.wheels=4;c.vel[2]=c.p.topSpeed*.25f;c.v=c.vel[2];
  CarInput input={0};input.brake=1;audioPlayerCar(name);starts=0;
  audioSkid(skidSoundLevel(&c,&input),0);
  int actualStarts=starts;int isSilent=car->skid<0;
  if(!isSilent){int id=car->skid;isSilent=R[id].nVar>0;for(unsigned k=0;k<R[id].nVar;k++)if(VAR[R[id].firstVar+k]!=blankFile)isSilent=0;}
  if(isSilent){silent++;if(starts)bad++;}else{audible++;if(starts!=1)bad++;}
  // Decode actual DSP in whole 512-frame blocks; ordinary bank skid must be audible.
  short pcm[FRAMES*2];int peak=0;for(int i=0;i<12;i++){audioHostMix(pcm,FRAMES);for(int k=0;k<FRAMES*2;k++)if(abs(pcm[k])>peak)peak=abs(pcm[k]);}
  if(!isSilent&&peak==0)bad++;
  audioSkid(0,0);input.brake=0;starts=0;if(skidSoundLevel(&c,&input)!=0)bad++;
  c.grounded=0;input.brake=1;if(skidSoundLevel(&c,&input)!=0)bad++;
  c.grounded=1;c.vel[2]=c.v=0;input=(CarInput){0};if(skidSoundLevel(&c,&input)!=0)bad++;
  printf("%s silent=%d skidStarts=%d pcmPeak=%d\n",name,isSilent,actualStarts,peak);
 }
 audioShutdown();printf("%s profiles=%d audible=%d authoredSilent=%d failures=%d\n",bad?"FAIL":"PASS",audible+silent,audible,silent,bad);return !!bad;
}
