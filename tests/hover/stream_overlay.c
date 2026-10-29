// Actual SAB/SAP, public engine lifecycle and shared DSP state, no fake mixer.
#include "../../viewer/audio.c"
static short out[MIX_FRAMES*2];
static unsigned pcmHash=2166136261u;
static void tick(int n){for(int i=0;i<n;i++){audioHostMix(out,MIX_FRAMES);for(unsigned k=0;k<sizeof(out)/sizeof(out[0]);k++){pcmHash^=(unsigned short)out[k];pcmHash*=16777619u;}}}
static int test(int yes,const char *why){if(!yes)printf("FAIL %s\n",why);return !yes;}
int main(int argc,char **argv){
 if(argc!=2 || audioInit(argv[1]))return 2;
 int fail=0;audioTestSeed(1);
 int music=audioTrack("test_music"),amb=audioTrack("test_amb"),dialog=audioTrack("test_dialog"),pos=audioTrack("test_pos");
 audioMusic(music,0);audioAmbience(amb,0);audioStream(AUDIO_ST_DIALOG,dialog,0);audioStream(AUDIO_ST_POSITIONAL,pos,0);tick(20);
 const char *names[]={"ship","icecream","IStruck","nuctruck","votetruc"};
 for(int c=0;c<5;c++){
  audioPlayerCar(names[c]);audioEngine(0,120,0,AUDIO_ENGINE_ON);tick(20);
  int track=audioStreamTrack(AUDIO_ST_CAR_OVERLAY);unsigned serial=audioStreamRequestSerial(AUDIO_ST_CAR_OVERLAY);
  fail+=test(track>=0,"stream overlay starts");
  int k=MIX_NVOICE+AUDIO_ST_CAR_OVERLAY;
  fail+=test(J->v[k].on && voices[k].bus==AUDIO_BUS_CAR,"actual car-bus DSP voice");
  if(covs && covf && carIdx<(int)ncovs){
    const CarStreamProfile *p=&covs[carIdx];int exact=0;
    for(unsigned j=0;j<p->count;j++){const CarStreamVariant *v=&covf[p->first+j];if(v->track==track && fabsf(voices[k].vol-v->trim)<1e-6f)exact=1;}
    fail+=test(exact,"exact selected resource trim");
  }
  fail+=test(audioStreamTrack(0)==music && audioStreamTrack(1)==amb && audioStreamTrack(3)==pos,"music/ambience/pos untouched");
  if(track>=0){
   fail+=test(T[track].flags&1,"authored loop flag");
   for(int i=0;i<10;i++){audioEngine(0,120,0,AUDIO_ENGINE_ON);tick(2);}
   fail+=test(audioStreamRequestSerial(4)==serial,"no frame-by-frame restart");
   fail+=test(voices[k].vol>0 && voices[k].vol<=1,"resource trim applied");
   // Cross the actual loop end; no one-pass truncation and no underrun.
   unsigned samples=T[track].loopEnd+2048;int buffers=(int)((double)samples/T[track].rate*RATE/MIX_FRAMES)+4;
   tick(buffers);fail+=test(audioStreamTrack(4)==track && J->v[k].on,"loop remains active past source end");
  }
  audioEngine(0,120,0,0);tick(20);fail+=test(audioStreamTrack(4)==-1 && !J->v[k].on,"exit stops overlay");
  printf("%s track%d serial%u\n",names[c],track,serial);
 }
 audioPlayerCar("ship");audioEngine(0,120,0,AUDIO_ENGINE_ON);tick(20);
 audioPlayerCar("gramR_v");tick(20);fail+=test(audioStreamTrack(4)==-1,"switch stops old streaming overlay");
 audioEngine(0,120,0,AUDIO_ENGINE_ON);tick(20);fail+=test(audioPlaying(E.ovl),"resident rocket overlay still plays");
 fail+=test(audioStreamTrack(4)==-1,"resident overlay does not borrow stream");
 audioEngine(0,120,0,0);tick(20);
 AudioStats st;audioStats(&st);fail+=test(st.underruns==0 && st.dropped==0,"no underruns/dropped voices");
 audioShutdown();fail+=test(!haveMusic && !E.ovl,"level shutdown clears voices");
 printf("%s stream overlays failures%d pcm=%08x\n",fail?"FAIL":"PASS",fail,pcmHash);return fail?1:0;
}
