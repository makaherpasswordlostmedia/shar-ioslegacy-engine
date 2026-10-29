#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "audio.h"
#include "fe_audio.h"
static short pcm[1024];static int failures;
static void ck(const char *name,int ok,int got,int want){printf("CHECK %s %s got=%d want=%d\n",name,ok?"PASS":"FAIL",got,want);failures+=!ok;}
static int tick(void){audioHostMix(pcm,512);int nonzero=0;for(int i=0;i<1024;i++)nonzero+=pcm[i]!=0;return nonzero;}
static unsigned tableHash(void){unsigned h=2166136261u;for(int i=0;i<audioTrackCount();i++){const char *s=audioTrackName(i);while(*s)h=(h^(unsigned char)*s++)*16777619u;}return h;}
int main(int argc,char **argv){
 if(argc!=4)return 2;setvbuf(stdout,NULL,_IONBF,0);if(audioInit(argv[1]))return 2;
 audioTestForceUnity(1);int before=audioTrackCount();unsigned hash=tableHash();
 ck("missing_bank_rejected",feAudioLoad("missing-fe-audio.sap")<0,feAudioStatus(),-1);
 int loaded=feAudioLoad(argv[2]);ck("separate_NIS_bank12",loaded==12,loaded,12);
 if(loaded!=12)return 1;
 ck("level_track_count_unchanged",audioTrackCount()==before,audioTrackCount(),before);ck("level_track_names_unchanged",tableHash()==hash,1,1);
 for(int k=0;k<13;k++){
  int index=k==12?5:k<7?k+1:0,seg=k<7||k==12?-1:k-7;const char *name=feAudioName(index,seg);int id=audioExtraTrack(name);feAudioStop();
  ck("name_bound_to_extra_id",id==0x4000+(k==12?4:k),id,0x4000+(k==12?4:k));
  int loop,next,bus;unsigned ns,ls,le;ck("native_SAP_info",audioTestTrackInfo(id,&loop,&next,&bus,&ns,&ls,&le),1,1);
  ck("authored_nonloop_dialogue",!loop&&next==-1&&bus==2,bus,2);
  AudioStats st;audioStats(&st);unsigned io=st.ioBytes;
  feAudioEvent(180,index,seg);unsigned serial=audioStreamRequestSerial(AUDIO_ST_DIALOG);
  ck("event180_accepted",feAudioStatus()==1,feAudioStatus(),1);
  int sounded=0;for(int i=0;i<173;i++)sounded+=tick();audioStats(&st);
  ck("prepare_two_seconds_silent",sounded==0,sounded,0);ck("prepare_no_playing_voice",st.track[AUDIO_ST_DIALOG]==-1,st.track[AUDIO_ST_DIALOG],-1);
  ck("prepare_real_IO",st.ioBytes>io,(int)(st.ioBytes-io),1);ck("prepare_ring_filled",feAudioPrepared(),feAudioPrepared(),1);
  feAudioEvent(181,index,seg);ck("event181_accepted",feAudioStatus()==1,feAudioStatus(),1);
  ck("start_reuses_request_and_prefetch",audioStreamRequestSerial(AUDIO_ST_DIALOG)==serial,(int)audioStreamRequestSerial(AUDIO_ST_DIALOG),(int)serial);
  char file[512];snprintf(file,sizeof file,"%s/%s%s.raw",argv[3],name,k==12?"-repeat":"");FILE *f=fopen(file,"wb");if(!f)return 2;
  int started=0,ended=0,nonzero=0;unsigned frames=0;
  for(unsigned guard=0;guard<ns/512+128;guard++){
   nonzero+=tick();audioStats(&st);if(st.track[AUDIO_ST_DIALOG]==id)started=1;
   if(started){fwrite(pcm,sizeof(short),1024,f);frames+=512;}
   if(started&&st.track[AUDIO_ST_DIALOG]<0){ended=1;break;}
  }
  fclose(f);ck("actual_backend_voice_starts",started,started,1);ck("actual_backend_voice_ends",ended,ended,1);ck("actual_backend_PCM_nonzero",nonzero>0,nonzero,1);
  printf("CLIP %s index=%d seg=%d id=%d srcframes=%u outputframes=%u seconds=%.6f\n",name,index,seg,id,ns,frames,audioTrackSeconds(id));
 }
 // All authored FE clips are 24 kHz. Exercise real rate/pitch1, not unity step.
 audioTestForceUnity(0);feAudioEvent(180,0,0);for(int i=0;i<173;i++)tick();feAudioEvent(181,0,0);
 int rateid=audioExtraTrack(feAudioName(0,0)),rateStarted=0,rateEnded=0,rateFrames=0;AudioStats rs;
 for(int guard=0;guard<1000;guard++){tick();audioStats(&rs);if(rs.track[AUDIO_ST_DIALOG]==rateid)rateStarted=1;if(rateStarted)rateFrames+=512;if(rateStarted&&rs.track[AUDIO_ST_DIALOG]<0){rateEnded=1;break;}}
 int wantFrames=(int)(audioTrackSeconds(rateid)*44100.f);
 ck("actual_24000_to_44100_rate_pitch1",rateStarted&&rateEnded&&abs(rateFrames-wantFrames)<=2048,rateFrames,wantFrames);audioTestForceUnity(1);
 // Another owner's mission speech may replace a pending FE cue; FE never stops it.
 int dialog=-1,music=-1,amb=-1;for(int t=0;t<audioTrackCount();t++){if(audioTrackBus(t)==2&&dialog<0)dialog=t;if(audioTrackBus(t)==0&&music<0)music=t;if(audioTrackBus(t)==1&&amb<0)amb=t;}
 ck("base_mission_voice_available",dialog>=0,dialog,0);
 if(dialog>=0){
  feAudioStop();feAudioEvent(180,1,-1);for(int i=0;i<4;i++)tick();audioStream(AUDIO_ST_DIALOG,dialog,0);unsigned s=audioStreamRequestSerial(AUDIO_ST_DIALOG);
  feAudioEvent(181,1,-1);ck("mission_takeover_rejects_stale_FE",feAudioStatus()==-2,feAudioStatus(),-2);feAudioFree();
  ck("free_preserves_mission_request",audioStreamRequestSerial(AUDIO_ST_DIALOG)==s&&audioStreamTrack(AUDIO_ST_DIALOG)==dialog,audioStreamTrack(AUDIO_ST_DIALOG),dialog);
  for(int i=0;i<4;i++)tick();feAudioLoad(argv[2]);feAudioEvent(180,2,-1);ck("active_mission_speech_not_overwritten",feAudioStatus()==-2&&audioStreamTrack(AUDIO_ST_DIALOG)==dialog,feAudioStatus(),-2);
  audioStream(AUDIO_ST_DIALOG,-1,0);for(int i=0;i<16;i++)tick();
 }
 audioTestForceUnity(0);audioMusic(music,0);audioAmbience(amb,0);for(int i=0;i<8;i++)tick();
 unsigned ms=audioStreamRequestSerial(AUDIO_ST_MUSIC),as=audioStreamRequestSerial(AUDIO_ST_AMBIENCE);
 feAudioEvent(180,0,4);for(int i=0;i<173;i++)tick();
 ck("FE_prepare_preserves_music_ambient",ms==audioStreamRequestSerial(0)&&as==audioStreamRequestSerial(1)&&audioStreamTrack(0)==music&&audioStreamTrack(1)==amb,1,1);
 feAudioStop();for(int i=0;i<8;i++)tick();ck("cancelled_prepare_does_not_start",audioStreamTrack(AUDIO_ST_DIALOG)<0,audioStreamTrack(AUDIO_ST_DIALOG),-1);
 feAudioEvent(181,0,4);ck("181_without_matching180_rejected",feAudioStatus()==-2,feAudioStatus(),-2);
 feAudioEvent(180,0,5);ck("invalid_Homer_segment_rejected",feAudioStatus()==-1,feAudioStatus(),-1);
 feAudioFree();audioShutdown();ck("shutdown_invalidates_extra_bank",audioExtraTrack("FE_Gag_Nick")<0,audioExtraTrack("FE_Gag_Nick"),-1);
 printf("RESULT %s failures=%d\n",failures?"FAIL":"PASS",failures);return !!failures;
}
