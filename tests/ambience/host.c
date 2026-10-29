/* Actual sound/audio mixer, CPU. Expectations supplied from the disc by gate.py.
   dBFS is measured output; PS2 calibration is checked separately by amb161 (L1 only). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "sound.h"
#include "audio.h"
/* Owner instruction 422; dependency 71ac25a. Independent expected contract, not queried from implementation. */
#define EXPECT_STREET_DB (-3.)
static int fails;
static const char *pack;
static void check(const char *tag,const char *name,int ok) { printf("CHECK %s %s %s\n",tag,name,ok?"PASS":"FAIL");fails+=!ok; }
static void begin(void) {
 if(sndInit(pack)<0){printf("FAIL init %s\n",sndError());exit(2);}
 sndUserVolumes(1,1,1,1); sndOnFoot(1);sndMode(SND_MODE_ONFOOT);sndMusic(SND_MUS_OFF);
 audioListener(4000,4000,4000,1,0); sndLevelStart(4000,4000,4000);
#ifdef AMBIENCE_C3_OLD
 sndRoomAmbOld=1;
#endif
}
static const char *track(void) { int t=audioStreamTrack(AUDIO_ST_AMBIENCE);return t<0?"-":audioTrackName(t); }
static double measure(void) {
 short buf[1024];double e=0;long n=0;
 for(int f=0;f<44100*4;f+=512) { audioHostMix(buf,512);
  if(f>=44100)for(int k=0;k<1024;k++){double x=buf[k]/32768.;e+=x*x;n++;}
 }
 return 20*log10(sqrt(e/n)+1e-12);
}
static double render(const char *name,int mode,int raw,const char *room) {
 begin();sndMode(mode);if(room&&strcmp(room,"-"))sndRoom(room);audioAmbience(audioTrack(name),0);
 if(raw) {audioMaster(1);audioBus(AUDIO_BUS_AMBIENCE,1.f/audioTestAmbGain());audioStreamSet(AUDIO_ST_AMBIENCE,1.f,0);}
 double db=measure();sndShutdown();return db;
}
/* Match the same fade/ADPCM phase as the actual enter/exit sequence before changing only gain.
   Comparing the initial startup window to an exit window measures the clip's different phase. */
static double rawRoomCycle(const char *room,int exiting) {
 begin();measure();sndRoom(room);
 if(!exiting){audioMaster(1);audioBus(AUDIO_BUS_AMBIENCE,1.f/audioTestAmbGain());audioStreamSet(AUDIO_ST_AMBIENCE,1,0);}
 double db=measure();
 if(exiting){sndRoom(NULL);audioMaster(1);audioBus(AUDIO_BUS_AMBIENCE,1.f/audioTestAmbGain());audioStreamSet(AUDIO_ST_AMBIENCE,1,0);db=measure();}
 sndShutdown();return db;
}
int main(int argc,char **argv) {
 if(argc!=5)return 2;pack=argv[1];float normal=atof(argv[3]),foot=atof(argv[4]);
 FILE *spec=fopen(argv[2],"r");if(!spec)return 2;
 char kind[20],name[80],want[80],start[80]="";
 while(fscanf(spec,"%19s %79s %79s",kind,name,want)==3) {
  if(!strcmp(kind,"START")){strcpy(start,name);begin();measure();check("start",name,!strcmp(track(),name));sndShutdown();}
  if(!strcmp(kind,"ROOM")) {
   int authored;if(fscanf(spec,"%d",&authored)!=1)return 3;
   begin();measure();sndRoom(name);double db=measure();check("room",name,!strcmp(track(),want));
   printf("MEASURE room %s track=%s dbfs=%.3f\n",name,track(),db);
   sndRoom(NULL);double out=measure();check("exit",name,!strcmp(track(),start));sndShutdown();
   double rawRoom=rawRoomCycle(name,0),rawStreet=rawRoomCycle(name,1);
   double base=20*log10(.7*foot);
   check("room-gain",name,fabs(db-rawRoom-base-(authored?0.:EXPECT_STREET_DB))<.15);
   check("exit-gain",name,fabs(out-rawStreet-base-EXPECT_STREET_DB)<.15);
   printf("MEASURE room-gain %s gain=%.3f target=%.3f exit_gain=%.3f target=%.3f\n",name,db-rawRoom,base+(authored?0.:EXPECT_STREET_DB),out-rawStreet,base+EXPECT_STREET_DB);
  }
  if(!strcmp(kind,"GATE")) {
   float a[3],b[3];if(fscanf(spec,"%f %f %f %f %f %f",a,a+1,a+2,b,b+1,b+2)!=6)return 3;
   begin();sndLevelStart(a[0],a[1],a[2]);
   sndFrame(.016f,4000,4000,4000,1,0,b[0],b[1],b[2]);
   audioStream(AUDIO_ST_POSITIONAL,-1,0);measure();
   check("gate",name,!strcmp(track(),want));sndShutdown();
  }
  if(!strcmp(kind,"TRACK")) {
   double raw=render(name,SND_MODE_ONFOOT,1,want), f=render(name,SND_MODE_ONFOOT,0,want), n=render(name,SND_MODE_NORMAL,0,want);
   double offset=!strcmp(want,"-")?EXPECT_STREET_DB:0.;double fw=20*log10(.7*foot)+offset,nw=20*log10(.7*normal)+offset;
   printf("MEASURE track %s raw=%.3f foot=%.3f normal=%.3f foot_gain_db=%.3f normal_gain_db=%.3f\n",name,raw,f,n,f-raw,n-raw);
   check("foot-gain",name,isfinite(f)&&fabs(f-raw-fw)<.15);
   check("normal-gain",name,isfinite(n)&&fabs(n-raw-nw)<.15);
  }
 }
 fclose(spec);printf("RESULT %s failures=%d\n",fails?"FAIL":"PASS",fails);return !!fails;
}
