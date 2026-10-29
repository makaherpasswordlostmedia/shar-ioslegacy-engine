#include "bonus_audio.h"
#include "sound.h"
#include "audio.h"
#include <stdio.h>
#include <string.h>
static int beeps,crashes,fails;static double energy;
static void note(const char*s){if(strstr(s,"countdown_beeps"))beeps++;if(strstr(s,"_crash"))crashes++;}
static void mix(int n){short b[1024];for(int j=0;j<n;j++){audioHostMix(b,512);for(int k=0;k<1024;k++)energy+=(double)b[k]*b[k];}}
static void need(const char*n,int ok){printf("%s %s\n",ok?"PASS":"FAIL",n);fails+=!ok;}
int main(int argc,char**argv){
 if(argc!=2||sndInit(argv[1]))return 2;sndLogHook(note);
 BonusRace r={0};Car p={0};MsnCars m={0};BrAudio a;
 p.p.topSpeed=40;p.ry=1;r.count=BR_COUNT_S;brAudioInit(&a);
 const float count[3]={BR_COUNT_S,2.f,1.f};
 for(int i=0;i<3;i++){r.count=count[i];brAudioFrame(&a,&r,&p,"famil_v",&m,.02f,0,0);mix(10);}
 need("three native countdown beeps",beeps==3);need("actual mixer countdown PCM",energy>1e8);
 brAudioFrame(&a,&r,&p,"famil_v",&m,.02f,0,1);mix(10);
 need("pause does not repeat beep",beeps==3);
 r.state=BR_RACE;brAudioFrame(&a,&r,&p,"famil_v",&m,.02f,1,0);mix(80);
 need("native racing stream",audioStreamTrack(AUDIO_ST_MUSIC)==audioTrack("casio_tune01"));
 need("native car profiles",audioCarProfile("famil_v")>=0&&audioCarProfile("homer_v")>=0);
 need("native NPC profiles",audioCarProfile("pickupA")>=0&&audioCarProfile("cLimo")>=0&&audioCarProfile("otto_v")>=0);
 p.hardV=10;brAudioFrame(&a,&r,&p,"famil_v",&m,.02f,1,0);mix(20);
 need("minigame crash resource",crashes==1);p.hardV=0;
 brAudioResult(&a,1);mix(10);need("winner stream",audioStreamTrack(AUDIO_ST_MUSIC)==audioTrack("win_mini_game"));
 unsigned serial=audioStreamRequestSerial(AUDIO_ST_MUSIC);brAudioResult(&a,1);
 need("result requested once",serial==audioStreamRequestSerial(AUDIO_ST_MUSIC));
 brAudioStop(&a);mix(10);need("music stopped on exit",audioStreamTrack(AUDIO_ST_MUSIC)<0);
 brAudioInit(&a);brAudioResult(&a,0);mix(10);
 need("loser stream",audioStreamTrack(AUDIO_ST_MUSIC)==audioTrack("lose_mini_game02"));
 brAudioStop(&a);mix(20);AudioStats s;audioStats(&s);need("exit clears voices",s.voices==0);sndShutdown();
 return fails?1:0;
}
