// Actual public street-voice API, real SAP streams and the shared mixer used
// by Allegrex/ME. Listener and speaker move independently while a line plays.
#include "../../viewer/audio.c"
#include "sound.h"
static short output[MIX_FRAMES*2];
static int checks,failures;
static void expect(int ok,const char*why){checks++;if(!ok){failures++;printf("FAIL %s\n",why);}}
static void buffers(int n){for(int i=0;i<n;i++)audioHostMix(output,MIX_FRAMES);}
static void listener(float x,float rx){audioListener(x,0,0,rx,0);buffers(2);}
int main(int argc,char**argv){
 if(argc!=2)return 2;
 for(int driver=0;driver<2;driver++){
  if(sndInit(argv[1])<0)return 2;audioListener(0,0,0,1,0);
  int started=driver?sndDriverSayAt(SND_DRV_WAY,0,10,0,0):sndPedSayAt(SND_PED_HIT,0,10,0,0);
  expect(started==1,"street fixture starts");buffers(3);
  MixVoice*v=&J->v[MIX_NVOICE+AUDIO_ST_DIALOG];
  expect(v->on && v->point.on && v->point.p[0]==160,"speaker source stored in shared DSP");
  expect(v->gr>v->gl,"right-hand speaker pans right");
  int track=audioStreamTrack(AUDIO_ST_DIALOG);
  listener(20,1);expect(v->gl>v->gr,"walking past speaker pans left without restarting line");
  expect(audioStreamTrack(AUDIO_ST_DIALOG)==track,"movement retains original stream");
  listener(20,-1);expect(v->gr>v->gl,"camera rotation changes stereo side");
  expect(sndStreetMove(30,0,0),"moving source still owns dialogue");buffers(2);
  expect(v->point.p[0]==480 && v->gl>v->gr,"speaker follows actor rather than trigger position");
  listener(100,1);expect(!v->gl&&!v->gr,"distant voice fades to silence");
  listener(30,1);expect(v->gl>0 && v->gl==v->gr,"approaching current speaker restores centered voice");
  // A new scripted conversation clears the street source even when it
  // requests the same underlying track: ownership follows the request serial.
  audioStream(AUDIO_ST_DIALOG,track,0);buffers(3);
  expect(!v->point.on,"next conversation does not inherit street position");
  expect(!sndStreetMove(-40,0,0),"old actor cannot attach itself to the replacement dialogue");
  sndStreetStop();expect(audioStreamTrack(AUDIO_ST_DIALOG)==track,"stale actor does not stop replacement conversation");
  sndShutdown();
 }
 printf("%s street spatial checks=%d failures=%d\n",failures?"FAIL":"PASS",checks,failures);
 return failures?1:0;
}
