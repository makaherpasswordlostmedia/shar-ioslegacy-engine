/* Real audio mixer + sound event dispatch; no device, speakers or emulator. */
#include "../../viewer/audio.c"
#include "../../viewer/sound.h"
#include "../../viewer/msn_audio.h"
static int failures, checks;
static short pcm[MIX_FRAMES*2];
static void check(int ok,const char *why){checks++;if(!ok){failures++;printf("FAIL %s\n",why);}}
static void tick(void){for(int i=0;i<4;i++)audioHostMix(pcm,MIX_FRAMES);}
static int silentSkid(int r){
 if(!strcmp(R[r].name,"blank"))return 1;
 if(blankFile<0 || !R[r].nVar)return 0;
 for(unsigned i=0;i<R[r].nVar;i++)if(VAR[R[r].firstVar+i]!=blankFile)return 0;
 return 1;
}
static char lastEvent[40],lastTrack[40];
static int musicEvent(void *u,const char *e,const char **track){
 (void)u;snprintf(lastEvent,sizeof lastEvent,"%s",e);int result=sndMusicEvent(e,track);
 snprintf(lastTrack,sizeof lastTrack,"%s",result>0?*track:"-");return result;
}
int main(int argc,char **argv){
 if(argc!=2 || sndInit(argv[1]))return 2;
 const SabCar *profiles=(const SabCar*)(bank+H->carOff);
 for(unsigned i=0;i<H->ncar;i++){
  const SabCar *p=&profiles[i];int got=audioPlayerCar(p->name);
  check(got==(int)i && car->engine==p->engine,"own engine profile");
  check(car->horn==p->horn,"no foreign horn for unresolved authored clip");
  audioEngine(0,120,0,AUDIO_ENGINE_ON);tick();
  check(audioPlaying(E.eng),"idle engine reaches mixer");
  audioEngine(50,120,1,AUDIO_ENGINE_ON);tick();
  check(audioPlaying(E.eng),"throttle reaches mixer");
  audioHorn(1);tick();check(p->horn<0 || audioPlaying(E.horn),"own horn reaches mixer");audioHorn(0);
  for(int dirt=0;dirt<2;dirt++){
   int ri=dirt?p->dirtSkid:p->skid;
   audioSkid(.8f,dirt);tick();
   check(ri<0 || silentSkid(ri) || (audioPlaying(E.skid) && E.skidRes==ri),"authored road/dirt skid");
   if(ri>=0 && silentSkid(ri))check(!audioPlaying(E.skid),"authored blank is silent");
   audioSkid(0,dirt);tick();
  }
  audioEngine(0,120,0,0);tick();
 }
 sndPlayerCarState(profiles[0].name,1);
 check(!strcmp(car->name,"huskA"),"wreck uses huskA engine and skid profile");
 check(car->horn<0,"undefined wreck horn does not borrow level horn");
 sndPlayerCarState(profiles[0].name,0);
 check(!strcmp(car->name,profiles[0].name),"repair restores original sound profile");
 MsnAudioBackend b={0};b.music_event=musicEvent;
 /* Native IsBonusMission explicitly excludes the sr prefix, not gr. */
 {MsnAudio a;msnAudioInit(&a,&b);msnAudioMissionStart(&a,"gr1",1);
  check(!strcmp(lastEvent,"Bonus_start"),"wager race retains native bonus music family");}
 for(int race=1;race<=3;race++){
  char id[8],want[40];snprintf(id,sizeof id,"sr%d",race);
  MsnAudio a;msnAudioInit(&a,&b);lastEvent[0]=0;msnAudioMissionStart(&a,id,1);
  printf("RACE %s bonus=1 event=%s track=%s\n",id,lastEvent,lastTrack);
  snprintf(want,sizeof want,"StreetRace0%d_start",race);
  check(!strcmp(lastEvent,want) && a.started,"street race starts authored event");
  msnAudioTick(&a,.016f,1,-1);snprintf(want,sizeof want,"StreetRace0%d_get_out_of_car",race);
  check(!strcmp(lastEvent,want),"street race exit event");
  msnAudioSuffix(&a,"_win");snprintf(want,sizeof want,"StreetRace0%d_win",race);
  check(!strcmp(lastEvent,want),"street race result event");
 }
 /* Every exported event passes through the actual MEVT lookup and streaming
    request. Python independently verifies its file, repeat and next chain. */
 unsigned size=0;const unsigned char *ext=audioBankExt(&size);
 if(!ext || size<8)return 2;
 unsigned nsec=*(const unsigned*)(ext+4);int nevent=0;
 for(unsigned s=0;s<nsec;s++)if(!memcmp(ext+8+s*16,"MEVT",4)){
  const unsigned *sec=(const unsigned*)(ext+12+s*16);
  for(unsigned i=0;i<sec[1];i++){
   const unsigned char *e=ext+sec[0]+36*i;const char *track=0;int n=e[34];
   int result=sndMusicEvent((const char*)e,&track);tick();
   check(result==(n?1:0),"MEVT event reaches stream backend");
   if(n){int own=0;for(int j=0;j<n;j++){short ti;memcpy(&ti,e+28+2*j,2);if(!strcmp(track,audioTrackName(ti)))own=1;}
    check(own,"MEVT selects its authored alternatives");}
   nevent++;
  }
 }
 check(nevent>40,"full level event bank");
 printf("%s profiles=%u events=%d checks=%d failures=%d\n",failures?"FAIL":"PASS",H->ncar,nevent,checks,failures);
 sndShutdown();return failures?1:0;
}
