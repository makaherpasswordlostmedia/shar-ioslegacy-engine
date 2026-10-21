/* Real DEV resume, completed masks, NPC action replay and ordinary save round-trip.
 * EXPECT LEVEL HOMER MSN COLLECT. Old builds fail Rob350's full-progress contract. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "world.h"
#include "savegame.h"
static int fail,nchecks;
static void ck(const char *name,int ok,int got,int want) {
 printf("CHECK %s %s got=%d want=%d\n",name,ok?"PASS":"FAIL",got,want);nchecks++;fail+=!ok;
}
static void *readall(const char *path,size_t *n) {
 FILE *f=fopen(path,"rb");if(!f)return NULL;fseek(f,0,SEEK_END);*n=ftell(f);rewind(f);
 void *p=aligned_alloc(16,(*n+15)&~(size_t)15);if(!p||fread(p,1,*n,f)!=*n) {free(p);fclose(f);return NULL;}fclose(f);return p;
}
static unsigned markers;
static void marker(void *u,const MsnGiver *g,int on) { (void)u;if(g->mission_index>=0&&g->mission_index<32&&on) markers|=1u<<g->mission_index; }
int main(int argc,char **argv) {
 if(argc!=6)return 2;
 size_t pn;void *pack=readall(argv[4],&pn);if(!pack)return 2;MsnFile f;char err[160];
 if(msn_open(&f,pack,pn,err,sizeof err))return 2;int level=f.hdr->level;
 FILE *ef=fopen(argv[1],"r");if(!ef)return 2;int n,wantwasp=0;char list[128]={0},gmaskstr[32],line[512];unsigned long long gmask=0;
 while(fgets(line,sizeof line,ef)) {char ids[128],mask[32];int wasps;
  if(sscanf(line,"%d %127s %31s %d",&n,ids,mask,&wasps)==4&&n==level) {strcpy(list,ids);strcpy(gmaskstr,mask);wantwasp=wasps;gmask=strtoull(gmaskstr,NULL,0);}
 } fclose(ef);if(!*list)return 2;
 unsigned bm=0;int nb=0;char *ids[16],*next=strtok(list,",");while(next&&nb<16) {ids[nb++]=next;next=strtok(NULL,",");}
 for(int i=0;i<nb;i++) {int mi=msn_find_mission(&f,ids[i]);ck(ids[i],mi>=0,mi>=0,1);if(mi>=0)bm|=1u<<mi;}
 setenv("BW_COLLECT",argv[5],1);
 if(bwData(argv[2],argv[3],argv[4]))return 2;static BotWorld W;if(bwNew(&W))return 2;
 MsnProgress q={0};q.version=1;q.level=level;q.story=GAME_MSN_STORY_DEV;
 MsnGameApi view={0};view.nav.giver_icon=marker;markers=0;
 ck("dev.resume",gameMsnOpenAt(&W.msn,&W.G,pack,pn,&view,&q,err,sizeof err)==0,0,0);
 MsnRuntime *rt=&W.msn.rt;unsigned initial=rt->completed;
 int m7=msn_find_mission(&W.msn.f,"m7");
 ck("dev.full_bonus",(rt->completed&bm)==bm,__builtin_popcount(rt->completed&bm),nb);
 ck("dev.replay_markers",(markers&bm)==bm,__builtin_popcount(markers&bm),nb);
 ck("dev.story_guard",rt->cur==m7&&!(rt->completed>>m7&1)&&msn_free_roam(rt),rt->cur,m7);
 for(int i=0;i<nb;i++) {
  int mi=msn_find_mission(&W.msn.f,ids[i]);if(mi<0)continue;const MsnMission *m=&W.msn.f.missions[mi];
  ck("dev.NPC_binding",m->bonus_npc<W.msn.f.ncmds,m->bonus_npc<W.msn.f.ncmds,1);if(m->bonus_npc>=W.msn.f.ncmds)continue;const MsnCmd *cmd=&W.msn.f.cmds[m->bonus_npc];
  MsnEntity e={0};const char *npc=msn_arg_s(&W.msn.f,cmd,0);int have=rt->host.bonus_entity(rt->host.user,mi,npc,&e);
  ck("dev.giver",have,have,1);MsnWorld w={0};w.player=e.pos;w.on_foot=1;w.action=1;w.coins=99999;
  int near=msn_bonus_near(rt,&w);ck("dev.NPC_action",near==mi,near,mi);
  msn_tick(rt,1.f/60,&w);ck("dev.replay_started",rt->cur==mi,rt->cur,mi);
  msn_abort(rt);ck("dev.replay_keeps_progress",rt->completed==initial,rt->completed==initial,1);
 }
 if(!W.haveColl) return 2;
 svDevCollect(&W.coll);int total;
 int got=collectCount(&W.coll,level,COLL_GAGS,&total),wanted=__builtin_popcountll(gmask);
 ck("dev.gag_count",got==wanted&&total==wanted,got,wanted);
 ck("dev.gag_mask",collectGags(&W.coll,level)==gmask,collectGags(&W.coll,level)==gmask,1);
 ck("dev.cards",collectCards(&W.coll,level)==0x7f,collectCount(&W.coll,level,COLL_CARDS,NULL),7);
 ck("dev.wasps",collectCount(&W.coll,level,COLL_WASPS,NULL)==wantwasp,collectCount(&W.coll,level,COLL_WASPS,NULL),wantwasp);
 SaveGame saved,loaded;svClear(&saved);MsnProgress prog;msn_get_progress(rt,&prog);svCapture(&saved,&prog,&W.coll,&W.coins);saved.seq=1;
 unsigned char bytes[SV_BYTES];svWrite(&saved,bytes);ck("normal.roundtrip",svRead(bytes,sizeof bytes,&loaded)==SV_OK,0,0);
 svMsnProgress(&loaded,&q);markers=0;
 ck("normal.resume",gameMsnOpenAt(&W.msn,&W.G,pack,pn,&view,&q,err,sizeof err)==0,0,0);rt=&W.msn.rt;
 ck("normal.completed_preserved",rt->completed==initial,rt->completed==initial,1);
 ck("normal.no_dev_flag",!rt->dev_bonus_replay,rt->dev_bonus_replay,0);
 ck("normal.completed_markers_hidden",(markers&bm)==0,__builtin_popcount(markers&bm),0);
 int mi=msn_find_mission(&W.msn.f,ids[0]);const MsnCmd *cmd=&W.msn.f.cmds[W.msn.f.missions[mi].bonus_npc];MsnEntity e={0};
 rt->host.bonus_entity(rt->host.user,mi,msn_arg_s(&W.msn.f,cmd,0),&e);MsnWorld w={0};w.player=e.pos;w.on_foot=1;
 ck("normal.completed_NPC_closed",msn_bonus_near(rt,&w)==-1,msn_bonus_near(rt,&w),-1);
 for(int i=0;i<180;i++)bwStep(&W,0,0,0);
 ck("dev.no_auto_level_complete",rt->status!=MSN_LEVEL_DONE&&rt->cur==m7,rt->cur,m7);
 printf("RESULT L%d %s checks=%d failures=%d bonus=%d gags=%d/%d\n",level,fail?"FAIL":"PASS",nchecks,fail,nb,got,total);
 return fail?1:0;
}
