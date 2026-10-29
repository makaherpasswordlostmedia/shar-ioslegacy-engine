#include "bonus_audio.h"
#include "audio.h"
#include "sound.h"
#include <math.h>
#include <string.h>
void brAudioInit(BrAudio*a){
 memset(a,0,sizeof*a);a->lastBeep=-1;if(BONUS_SOUND_OLD)return;
 a->beep=sndId("countdown_beeps");a->music=audioTrack("casio_tune01");
 a->win=audioTrack("win_mini_game");a->lose=audioTrack("lose_mini_game02");
 sndMode(SND_MODE_NORMAL);sndMiniGame(1);
}
const char*brAudioTuneName(int track){
 static const char*const tune[5]={"casio_tune01","casio_tune02","casio_tune07","casio_tune08","casio_tune09"};
 return tune[((track-1)%5+5)%5];
}
void brAudioTune(BrAudio*a,int track){
 if(BONUS_SOUND_OLD||BONUS_TUNE_OLD)return;
 int id=audioTrack(brAudioTuneName(track));if(id>=0)a->music=id;
}
const char*brAudioTuneNameDir(int track,int reverse){
 if(!BONUS_TUNE_ONE_OLD)return"casio_tune09";
 if(!BONUS_TUNE_B01_OLD&&track==1)return reverse?"casio_tune07":"casio_tune09";
 return brAudioTuneName(track);
}
void brAudioTuneDir(BrAudio*a,int track,int reverse){
 if(BONUS_SOUND_OLD||BONUS_TUNE_OLD)return;
 int id=audioTrack(brAudioTuneNameDir(track,reverse));if(id>=0)a->music=id;
}
void brAudioFrame(BrAudio*a,const BonusRace*r,const Car*p,const char*name,const MsnCars*cars,float dt,float throttle,int paused){
 if(BONUS_SOUND_OLD)return;
 if(paused!=a->paused){a->paused=paused;sndPause(paused);}if(paused)return;
 if(r->state==BR_COUNT){
  int tick=BONUS_COUNT_PS2_OLD?(int)floorf(fmaxf(0,BR_COUNT_S-r->count)):3-brCountdownDigit(r->count);
  // Native digit cadence 3/2/1; beep binding remains port policy.
  if(tick>a->lastBeep&&tick<3){if(a->beep>=0)sndPlay2D(a->beep,1);a->lastBeep=tick;}
 }else if(r->state==BR_RACE&&!a->racing){a->racing=1;audioMusic(a->music,0);}
 // Top camera is over1km away: race listening point follows player (port policy)
 sndFrame(dt,p->x,p->ry,p->z,cosf(p->h),-sinf(p->h),p->x,p->h,p->z);
 float hit=p->hardV;
 audioWorldEngine(0,0,audioCarProfile(name),p->x,p->ry,p->z,p->v*3.6f,p->p.topSpeed*3.6f,r->state==BR_RACE?throttle:0,dt);
 int chosen[2]={-1,-1};float dist[2]={1e30f,1e30f};
 if(cars)for(int i=0;i<cars->n;i++)if(cars->c[i].on){
  const Car*k=&cars->c[i].car;hit=fmaxf(hit,k->hardV);float d=hypotf(k->x-p->x,k->z-p->z);
  if(d<dist[0]){dist[1]=dist[0];chosen[1]=chosen[0];dist[0]=d;chosen[0]=i;}else if(d<dist[1]){dist[1]=d;chosen[1]=i;}
 }
 for(int j=0;j<2;j++){
  int i=chosen[j];const McCar*c=i>=0?&cars->c[i]:NULL;
  if(c)audioWorldEngine(j+1,i+1,audioCarProfile(c->name),c->car.x,c->car.ry,c->car.z,c->car.v*3.6f,c->car.p.topSpeed*3.6f,r->state==BR_RACE&&c->car.acc>0?1:0,dt);
  else audioWorldEngine(j+1,-1,-1,0,0,0,0,0,0,dt);
 }
 if(hit>0)sndCarHitCar(hit,p->x,p->ry,p->z);
}
void brAudioResult(BrAudio*a,int winner){
 if(BONUS_SOUND_OLD||a->result)return;a->result=1;
 for(int i=0;i<AUDIO_WORLD_ENGINES;i++)audioWorldEngine(i,-1,-1,0,0,0,0,0,0,0);
 audioMusicOnce(winner?a->win:a->lose,0);
}
void brAudioStop(BrAudio*a){
 if(BONUS_SOUND_OLD)return;sndPause(0);sndMiniGame(0);
 for(int i=0;i<AUDIO_WORLD_ENGINES;i++)audioWorldEngine(i,-1,-1,0,0,0,0,0,0,0);
 audioMusic(-1,0);memset(a,0,sizeof*a);
}
