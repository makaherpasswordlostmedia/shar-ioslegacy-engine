// Public audio API + actual SAB/SAP; inspect actual shared DSP state after each mixed buffer
#include "../../viewer/audio.c"
static short output[MIX_FRAMES*2];
static void buffer(void){audioHostMix(output,MIX_FRAMES);}
static int check(int ok,const char *why){if(!ok)printf("FAIL %s\n",why);return !ok;}
int main(int argc,char **argv){
  if(argc!=2 || audioInit(argv[1])<0){printf("bank error %s\n",audioError());return 2;}
  int failures=0;audioListener(0,0,0,1,0);audioEnginePosition(10,0,0,1);
  audioEngine(25,120,.7f,AUDIO_ENGINE_ON);buffer();
  int k=(E.eng&255)-1;failures+=check(k>=0,"engine handle");if(k<0)return 1;
  failures+=check(J->v[k].point.on && J->v[k].gr>J->v[k].gl,"engine outside, source on right");
  audioListener(20,0,0,1,0);buffer();
  failures+=check(J->v[k].point.p[0]==160 && J->v[k].gl>J->v[k].gr,"parked motor stayed at car after walking past");
  audioListener(20,0,0,-1,0);buffer();failures+=check(J->v[k].gr>J->v[k].gl,"camera right reversed");
  audioListener(80,0,0,1,0);buffer();failures+=check(!J->v[k].gl&&!J->v[k].gr,"motor beyond audible distance");
  audioEnginePosition(10,0,0,0);buffer();failures+=check(!J->v[k].point.on && J->v[k].gl==J->v[k].gr && J->v[k].gl>0,"inside car preserves 2D engine level");
  audioListener(0,0,0,1,0);
  int h=audioPlayAtGain(car->horn,1,10,0,0,4,60);buffer();k=(h&255)-1;
  failures+=check(k>=0 && J->v[k].point.on && J->v[k].gr>J->v[k].gl,"world one-shot retained source");
  int two=audioPlayBus(car->horn,1,0,1,AUDIO_BUS_UI);buffer();k=(two&255)-1;
  failures+=check(k>=0 && !J->v[k].point.on && J->v[k].gl==J->v[k].gr,"UI remains centered");
  int track=-1;for(int i=0;i<audioTrackCount();i++)if(audioTrackBus(i)==AUDIO_BUS_AMBIENCE){track=i;break;}
  if(track>=0){audioStream(AUDIO_ST_POSITIONAL,track,.012f);audioStreamSet(AUDIO_ST_POSITIONAL,1,0);audioStreamAt(AUDIO_ST_POSITIONAL,10,0,0,4,60);
    for(int i=0;i<20;i++)buffer();k=MIX_NVOICE+AUDIO_ST_POSITIONAL;
    failures+=check(J->v[k].on && J->v[k].point.on && J->v[k].gr>J->v[k].gl,"positional ambient stream");
    audioStream(AUDIO_ST_DIALOG,track,.012f);audioStreamSet(AUDIO_ST_DIALOG,1,0);audioStreamAt(AUDIO_ST_DIALOG,10,0,0,4,60);
    for(int i=0;i<20;i++)buffer();k=MIX_NVOICE+AUDIO_ST_DIALOG;
    failures+=check(J->v[k].on && J->v[k].point.on && J->v[k].gr>J->v[k].gl,"world gag stream has shared positional gains");
    audioStream(AUDIO_ST_DIALOG,track,.012f);buffer();
    failures+=check(!J->v[k].point.on,"next mission voice clears old gag location");
  }else failures+=check(0,"ambient fixture");
  printf("%s audio API failures%d\n",failures?"FAIL":"PASS",failures);audioShutdown();return failures?1:0;
}
