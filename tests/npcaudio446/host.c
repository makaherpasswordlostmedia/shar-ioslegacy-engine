#include <stdio.h>
#include "../../viewer/audio.c"
static int bad,starts;
#define CHECK(x) do{if(!(x)){bad++;printf("FAIL line%d %s\n",__LINE__,#x);}}while(0)
static void note(int id,const char*why){(void)id;if(!strcmp(why,"skid"))starts++;}
static short pcm[FRAMES*2];
static int mix(int count){int peak=0;for(int f=0;f<count;f++){audioHostMix(pcm,FRAMES);for(int k=0;k<FRAMES*2;k++)if(abs(pcm[k])>peak)peak=abs(pcm[k]);}return peak;}
int main(int argc,char**argv){if(argc!=2||audioInit(argv[1]))return 2;audioNote=note;audioListener(0,0,0,1,0);
 const SabCar*profiles=(const SabCar*)(bank+H->carOff);int total=0,silent=0;
 for(unsigned j=0;j<H->ncar;j++){
  for(int slot=0;slot<AUDIO_WORLD_ENGINES;slot++){
   audioWorldEngine(slot,100+j,j,2,0,0,40,120,.5f,1.f/60);CHECK(worldEngine[slot].eng||worldEngine[slot].idle);
   CHECK(mix(12)>0);starts=0;audioWorldSkid(slot,0,0);CHECK(!worldEngine[slot].skid);
   int silentProfile=profiles[j].skid<0;
   if(!silentProfile){int id=profiles[j].skid;silentProfile=R[id].nVar>0;for(unsigned k=0;k<R[id].nVar;k++)if(VAR[R[id].firstVar+k]!=blankFile)silentProfile=0;}
   audioWorldSkid(slot,.8f,0);total++;
   if(silentProfile){silent++;CHECK(!worldEngine[slot].skid);}else{
    CHECK(worldEngine[slot].skid && starts==1);int handle=worldEngine[slot].skid;
    Voice*v=byHandle(handle);CHECK(v&&v->point.on&&v->point.p[0]==32);
    CHECK(mix(12)>0);audioWorldSkid(slot,0,0);mix(8);CHECK(!audioPlaying(handle));
    audioWorldSkid(slot,.8f,0);handle=worldEngine[slot].skid;
    audioWorldEngine(slot,-1,-1,0,0,0,0,1,0,1.f/60);mix(8);CHECK(!audioPlaying(handle));
   }
   audioWorldEngine(slot,-1,-1,0,0,0,0,1,0,1.f/60);mix(8);
  }
 }
 CHECK(!E.eng&&!E.skid);audioWorldSkid(-1,1,0);audioWorldSkid(AUDIO_WORLD_ENGINES,1,0);
 audioShutdown();printf("%s profiles×slots=%d authoredSilent=%d failures=%d\n",bad?"FAIL":"PASS",total,silent,bad);return !!bad;
}
