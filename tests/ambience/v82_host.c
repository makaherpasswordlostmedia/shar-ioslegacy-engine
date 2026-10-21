/* Read-only source acceptance: actual reader, playing status and mixed PCM.
 * fread wrapper is linked only into the test audio object; no production edits. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sound.h"
#include "audio.h"
static int phase=-1, seen[3];
static unsigned epoch;
static long lo[2], hi[2];
static const char *expected[2];
size_t v82Read(void *p,size_t size,size_t n,FILE *f) {
 long pos=ftell(f);size_t got=fread(p,size,n,f);
 int k=phase==1?1:0;
 if(phase>=0&&!seen[phase]&&got&&pos>=lo[k]&&pos<hi[k]) {
  seen[phase]=1;printf("READ phase=%d frames=%u bytes=%zu offset=%ld\n",phase,audioTestFramesOut()-epoch,got*size,pos);
 }
 return got;
}
static void note(int stream,int track,float fade,int held) {
 if(stream==AUDIO_ST_AMBIENCE)printf("REQUEST phase=%d name=%s fade=%.3f held=%d\n",phase,audioTrackName(track),fade,held);
}
static void render(FILE *pcm,int blocks) {
 short b[1024];int started=0;
 for(int i=0;i<blocks;i++) {
  audioHostMix(b,512);fwrite(b,sizeof b,1,pcm);AudioStats s;audioStats(&s);
  if(!started&&s.track[AUDIO_ST_AMBIENCE]>=0&&s.trackPos[AUDIO_ST_AMBIENCE]>0&&!strcmp(audioTrackName(s.track[AUDIO_ST_AMBIENCE]),expected[phase==1])) {
   started=1;printf("PLAY phase=%d frames=%u name=%s position=%.6f\n",phase,audioTestFramesOut()-epoch,audioTrackName(s.track[AUDIO_ST_AMBIENCE]),s.trackPos[AUDIO_ST_AMBIENCE]);
  }
 }
 AudioStats s;audioStats(&s);printf("SETTLED phase=%d name=%s position=%.6f underruns=%d\n",phase,s.track[1]<0?"-":audioTrackName(s.track[1]),s.trackPos[1],s.underruns);
}
int main(int argc,char **argv) {
 if(argc!=10)return 2;
 lo[0]=atol(argv[5]);hi[0]=atol(argv[6]);lo[1]=atol(argv[7]);hi[1]=atol(argv[8]);
 int mode=atoi(argv[9]);FILE *pcm=fopen(argv[2],"wb");if(!pcm)return 2;
 expected[0]=argv[3];expected[1]=argv[4];
 if(sndInit(argv[1])<0)return 3;
 sndUserVolumes(1,1,1,1);sndOnFoot(1);sndMode(SND_MODE_ONFOOT);sndMusic(SND_MUS_OFF);
 audioListener(4000,4000,4000,1,0);audioStreamNote=note;
 phase=0;epoch=audioTestFramesOut();sndLevelStart(4000,4000,4000);render(pcm,172);
 if(mode==2)sndRoomAmbOld=1;
 phase=1;epoch=audioTestFramesOut();sndRoom("SimpsonsHouse");
 if(mode==1)audioAmbience(audioTrack(argv[4]),.5f);
 render(pcm,259);
 phase=2;epoch=audioTestFramesOut();if(mode!=3)sndRoom(NULL);
 if(mode==1)audioAmbience(audioTrack(argv[3]),.5f);
 render(pcm,259);
 sndShutdown();fclose(pcm);return 0;
}
