#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "world.h"
#include "msn_audio_host.h"
static BotWorld W;
static const MsnAudioBackend *real;
static char lastKey[64],lastName[64];static int lastResult;
static int music(void *u,const char *ev,const char **name){
 int r=real->music_event(real->u,ev,name);snprintf(lastKey,sizeof lastKey,"%s",ev);
 snprintf(lastName,sizeof lastName,"%s",r>0?*name:"-");lastResult=r;return r;
}
typedef struct {int mi,phase,stage;char state[24],value[24],mid[16];} Case;
int main(int argc,char **argv){
 if(argc!=6)return 2;
 if(msnAudioHostLoad(argv[4]))return 2;real=msnAudioHostBackend();if(!real)return 2;
 MsnAudioBackend wrap=*real;wrap.music_event=music;
 if(bwData(argv[1],argv[2],argv[3]))return 2;gameMsnSetAudio(&wrap);bwNew(&W);
 Case cases[64];int n=0;
 for(unsigned mi=0;mi<W.msn.f.nmissions;mi++)for(int ph=0;ph<2;ph++){
  unsigned pi=ph?W.msn.f.missions[mi].main:W.msn.f.missions[mi].intro;if(pi==MSN_NONE16)continue;
  const MsnPhase *p=&W.msn.f.phases[pi];
  for(unsigned st=0;st<p->stage_count;st++){
   const MsnStage *s=&W.msn.f.stages[p->first_stage+st];
   for(unsigned k=0;k<s->cmd_count;k++){
    const MsnCmd *c=&W.msn.f.cmds[s->cmd_first+k];if(c->op!=MSN_OP_SETMUSICSTATE)continue;
    if(n==64)return 2;Case *a=&cases[n++];a->mi=mi;a->phase=ph;a->stage=st;
    snprintf(a->state,sizeof a->state,"%s",msn_arg_s(&W.msn.f,c,0));snprintf(a->value,sizeof a->value,"%s",msn_arg_s(&W.msn.f,c,1));
    snprintf(a->mid,sizeof a->mid,"%s",msn_str(&W.msn.f,W.msn.f.missions[mi].id));
   }
  }
 }
 for(int i=0;i<n;i++){
  Case *a=&cases[i];bwFree(&W);bwNew(&W);lastKey[0]=lastName[0]=0;
  W.msn.rt.cp_phase=a->phase;W.msn.rt.cp_stage=a->stage;msn_start_mission(&W.msn.rt,a->mi,1);
  printf("ACT\t%d\t%s\t%d\t%d\t%s\t%s\t%s\t%s\t%s\t%d\n",bwLevel(),a->mid,a->phase,a->stage,a->state,a->value,W.msn.audio.stateCode,W.msn.audio.stateValue,lastKey,lastResult);
 }
 FILE *f=fopen(argv[5],"r");if(!f)return 2;char line[256],state[32],value[32],ev[32];
 while(fgets(line,sizeof line,f)){
  if(sscanf(line,"%31s %31s %31s",state,value,ev)!=3)return 2;
  MsnAudio a;msnAudioInit(&a,&wrap);char mid[8];snprintf(mid,sizeof mid,"m%c",state[7]);msnAudioMissionStart(&a,mid,0);
  msnAudioState(&a,state,value);msnAudioEvent(&a,ev);
  printf("VAR\t%s\t%s\t%s\t%s\t%s\t%d\n",state,value,ev,lastKey,lastName,lastResult);
 }
 fclose(f);bwFree(&W);return 0;
}
