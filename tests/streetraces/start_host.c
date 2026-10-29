/* Actual GameMsn NPC action -> source intro dialogue backend -> authored countdown
 * -> first running main objective. Host teleports to live NPCs; no route/GPU claim. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
static int fail,ncheck,cd_n,cd_ms,cd_frames,go;
static void ck(const char *id,const char *what,int ok,int got,int want) {
 printf("CHECK %s %s %s got=%d want=%d\n",id,what,ok?"PASS":"FAIL",got,want);ncheck++;fail+=!ok;
}
static void event(void *u,const MsnEvent *e) {
 (void)u;if(e->type==MSN_EV_COUNTDOWN){cd_n++;cd_ms+=(int)lroundf(e->value*1000);go|=e->text&&!strcmp(e->text,"GO");printf("COUNTDOWN %s %.3f\n",e->text,e->value);}
}
static void *readall(const char *p,size_t *n) {
 FILE *f=fopen(p,"rb");if(!f)return NULL;fseek(f,0,SEEK_END);*n=ftell(f);rewind(f);void *b=malloc(*n);
 if(!b||fread(b,1,*n,f)!=*n){fclose(f);free(b);return NULL;}fclose(f);return b;
}
static void footAt(MsnVec3 p) {
 homerPlace(&W.homer,bwCol(),p.x+.2f,p.y,p.z,0);
 /* Exact host input position: no ground-height oracle affects NPC interaction. */
 W.homer.x=p.x+.2f;W.homer.y=p.y;W.homer.z=p.z;
}
int main(int argc,char **argv) {
 if(argc!=5)return 2;setvbuf(stdout,NULL,_IONBF,0);
 if(bwData(argv[2],argv[3],argv[4])||bwNew(&W))return 2;
 size_t size;void *pack=readall(argv[4],&size);if(!pack)return 2;char err[160];
 MsnProgress q={0};q.version=1;q.level=bwLevel();q.story=GAME_MSN_STORY_DEV;
 MsnGameApi view={0};view.on_event=event;
 if(gameMsnOpenAt(&W.msn,&W.G,pack,size,&view,&q,err,sizeof err))return 2;
 int geo,audio;bwMissionPacks(&geo,&audio);ck("level","original_audio_durations",audio,audio,1);
 FILE *f=fopen(argv[1],"r");if(!f)return 2;char line[512],id[24];int lv,stage,obj,laps,items,cd,count,up,vehicles,wp,nscenario=0;float timer,par;
 while(fgets(line,sizeof line,f)) {
  if(sscanf(line,"%d %23s %d %d %d %d %f %f %d %d %d %d %d",&lv,id,&stage,&obj,&laps,&items,&timer,&par,&cd,&count,&up,&vehicles,&wp)!=13||lv!=bwLevel())continue;
  nscenario++;GameMsn *m=&W.msn;MsnRuntime *rt=&m->rt;int mi=msn_find_mission(&m->f,id);
  ck(id,"pack_mission",mi>=0,mi,0);if(mi<0)continue;
  const MsnMission *ms=&m->f.missions[mi];int bind=ms->bonus_npc<m->f.ncmds;
  ck(id,"npc_binding",bind,bind,1);if(!bind)continue;
  const MsnCmd *c=&m->f.cmds[ms->bonus_npc];MsnEntity e={0};const char *npc=msn_arg_s(&m->f,c,0);
  int have=rt->host.bonus_entity&&rt->host.bonus_entity(rt->host.user,mi,npc,&e);
  ck(id,"live_giver",have,have,1);if(!have)continue;
  footAt(e.pos);ck(id,"action_hint",gameMsnWantsMissionAction(m),gameMsnWantsMissionAction(m),1);
  cd_n=cd_ms=cd_frames=go=0;int wallet=shopCoins(&m->shop);shopCoinsAdd(&m->shop,10000-wallet,0);
  GamePad p={0};p.hit=GP_TRIANGLE;gameMsnTick(m,&p,BW_DT);
  ck(id,"NPC_action_start",rt->cur==mi,rt->cur,mi);
  int frames=0,dialogue=0;
  for(;frames<3600&&rt->cur==mi&&rt->status!=MSN_FAILED;frames++) {
   if(rt->phase==1&&rt->stage==stage&&rt->status==MSN_RUNNING)break;
   memset(&p,0,sizeof p);
   if(rt->status==MSN_RUNNING&&rt->obj==MSN_OBJ_TALKTO&&rt->host.entity(rt->host.user,rt->target,&e)){footAt(e.pos);p.hit=GP_TRIANGLE;}
   if(rt->status==MSN_RUNNING&&rt->obj==MSN_OBJ_COINS)p.hit=GP_TRIANGLE;
   dialogue+=rt->obj==MSN_OBJ_DIALOGUE;cd_frames+=rt->status==MSN_COUNTDOWN;
   gameMsnTick(m,&p,BW_DT);
  }
  printf("START L%d %s frames=%d dialogue_frames=%d countdown_frames=%d go_token=%d phase=%d stage=%d status=%d obj=%d cars=%d waypoints=%d\n",lv,id,frames,dialogue,cd_frames,go,rt->phase,rt->stage,rt->status,rt->obj,m->cars.n,m->cars.nwp);
  ck(id,"main_running",rt->cur==mi&&rt->phase==1&&rt->stage==stage&&rt->status==MSN_RUNNING,rt->status,MSN_RUNNING);
  ck(id,"disc_objective",rt->obj==obj,rt->obj,obj);ck(id,"disc_laps",rt->laps==laps,rt->laps,laps);
  ck(id,"disc_items",rt->nitems==items,rt->nitems,items);ck(id,"disc_countdown_count",cd_n==count,cd_n,count);
  ck(id,"disc_countdown_duration",cd_ms==cd,cd_ms,cd);
  ck(id,"countdown_really_elapsed",cd_frames*1000/60>=cd&&cd_frames*1000/60<cd+count*18+18,cd_frames*1000/60,cd);
  if(up)printf("PORT_RULE %s UseElapsedTime initial=0 disc_SetStageTime=%.1f PS2_initial_unmeasured\n",id,timer);
  ck(id,up?"port_elapsed_initial":"disc_timer",fabsf(rt->remaining-(up?0:timer))<.05f,(int)(rt->remaining*1000),(int)((up?0:timer)*1000));
  ck(id,"disc_elapsed_mode",rt->timer_up==up,rt->timer_up,up);
  ck(id,"disc_stage_vehicles",m->cars.n==vehicles,m->cars.n,vehicles);
  ck(id,"disc_AI_waypoints",m->cars.nwp==wp,m->cars.nwp,wp);
  int locs=0;for(int k=0;k<rt->nitems;k++)locs+=msn_arg_loc(&m->f,rt->items[k],0)!=NULL;
  ck(id,"resolved_checkpoints",locs==items,locs,items);
  ck(id,"disc_par",fabsf(rt->par-par)<.001f,(int)rt->par,(int)par);
  if(!strcmp(id,"gr1")&&rt->cur==mi&&rt->status==MSN_RUNNING) {
   /* A real tick beyond disc ParTime with a healthy driver outside every checkpoint.
    * No timer/status/completion writes. The old runtime omits this failure rule. */
   MsnWorld empty={0};empty.player=(MsnVec3){1000000,0,1000000};empty.vehicle="current";empty.vehicle_health=1;empty.coins=10000;
   int frames_par=0;for(;frames_par<(int)((par+2)*60)&&rt->status==MSN_RUNNING;frames_par++)msn_tick(rt,BW_DT,&empty);
   ck(id,"disc_par_time_failure",rt->status==MSN_FAILED&&rt->fail==MSN_FAIL_PARTIME,rt->fail,MSN_FAIL_PARTIME);
   printf("PARTIME L%d frames=%d elapsed=%.3f source_limit=%.3f status=%d reason=%d\n",lv,frames_par,rt->remaining,par,rt->status,rt->fail);
  }
  gameMsnAbort(m);ck(id,"abort_free_roam",msn_free_roam(rt),msn_free_roam(rt),1);
 }
 fclose(f);ck("level","five_scenarios",nscenario==5,nscenario,5);
 printf("RESULT L%d %s scenarios=%d checks=%d failures=%d\n",bwLevel(),fail?"FAIL":"PASS",nscenario,ncheck,fail);return fail?1:0;
}
