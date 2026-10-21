// Родные команды MSN1 через установленный host; выбор ворот не перебивает UsePedGroup
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"
#include "traffic.h"
static BotWorld W;
static int bad;
static void check(const char *name,int good){if(!good)printf("FAIL %s\n",name);bad+=!good;}
static void step(Traffic *t,const float *pos){float eye[3]={pos[0],pos[1]+3,pos[2]-7},dir[3]={0,0,1};trafficUpdate(t,W.G.pWorld,&W.car,0,pos,eye,dir,1.f/30);}
int main(int argc,char **argv){
 if(argc!=4||bwData(argv[1],argv[2],argv[3])||bwNew(&W))return 2;
 Traffic *t=(Traffic*)bwTraffic();if(!t||!t->hd)return 2;t->maxCars=t->maxPeds=0;
 for(unsigned i=0;i<W.msn.f.nfiles;i++)printf("FILE %s\n",msn_str(&W.msn.f,W.msn.f.files[i]));
 int seen=0;unsigned groups=0;
 for(unsigned i=0;i<W.msn.f.ncmds;i++){
  const MsnCmd *cmd=&W.msn.f.cmds[i];if(cmd->op!=MSN_OP_USEPEDGROUP)continue;
  int desired=msn_arg_i(&W.msn.f,cmd,0);
  printf("SOURCE %s %u %d\n",msn_str(&W.msn.f,W.msn.f.files[cmd->file]),cmd->line,desired);seen++;
  check("authored-group-in-pack",desired>=0&&desired<(int)t->hd->nGroup);if(desired<0||desired>=(int)t->hd->nGroup)continue;
  unsigned before=W.msn.mg.op_calls[MSN_OP_USEPEDGROUP];
  MsnCall call={&W.msn.f,cmd,MSN_AT_SETUP,-1,-1};
  W.msn.rt.host.command(W.msn.rt.host.user,&call);
  check("runtime-dispatch",W.msn.mg.op_calls[MSN_OP_USEPEDGROUP]==before+1);
  check("mission-selection",t->group==desired&&t->missionPedGroup==desired);
  for(unsigned z=0;z<t->hd->nZone;z++) {step(t,t->zone[z].c);check("zone-cannot-override",t->group==desired);}
  int old=t->group;check("invalid-rejected",!trafficPedGroup(t,t->hd->nGroup)&&t->group==old);
  check("invalid-negative",!trafficPedGroup(t,-2)&&t->group==old);
  trafficReset(t,W.G.pWorld);check("teleport-retains-mission",t->group==desired);
  if(!(groups&(1u<<desired))&&t->grp[desired].n){
   groups|=1u<<desired;int spawned=0;t->maxPeds=TR_MAXPED;
   for(unsigned p=0;p<t->hd->nPath&&!spawned;p++){
    const TrPath *path=&t->path[p];float pos[3]={path->cx,W.car.y,path->cz};t->fresh=1;
    for(int fr=0;fr<3;fr++)step(t,pos);
    for(int k=0;k<TR_MAXPED;k++)if(t->ped[k].mode!=TRP_OFF){
     int member=0;for(int j=0;j<t->grp[desired].n;j++)member|=t->ped[k].model==t->grp[desired].model[j];
     check("spawn-model-from-author-group",member);spawned++;
    }
   }
   check("real-ped-spawn-observed",spawned>0);t->maxPeds=0;trafficReset(t,W.G.pWorld);
  }
  MsnEvent event={0};event.type=MSN_EV_CLEANUP;W.msn.rt.host.event(W.msn.rt.host.user,&event);
  check("cleanup-returns-zone",t->missionPedGroup==-1&&t->group==t->zoneGroup);
 }
 int actualStarts=0;
 for(unsigned m=0;m<W.msn.f.nmissions;m++){
  const MsnMission *mission=&W.msn.f.missions[m];
  unsigned phase=mission->intro!=MSN_NONE16?mission->intro:mission->main;
  if(phase==MSN_NONE16)continue;const MsnPhase *p=&W.msn.f.phases[phase];int desired=-1;
  for(unsigned k=0;k<p->setup_count;k++){
   const MsnCmd *cmd=&W.msn.f.cmds[p->setup_first+k];if(cmd->op==MSN_OP_USEPEDGROUP)desired=msn_arg_i(&W.msn.f,cmd,0);
  }
  if(desired<0)continue;
  msn_start_mission(&W.msn.rt,m,0);actualStarts++;
  check("real-intro-start-group",t->missionPedGroup==desired&&t->group==desired);
  for(unsigned z=0;z<t->hd->nZone;z++){step(t,t->zone[z].c);check("real-intro-zone",t->group==desired);}
  gameMsnAbort(&W.msn);
  // Abort штатно возвращает вступление; его UsePedGroup применяется снова после cleanup
  int after=-1;const MsnMission *next=&W.msn.f.missions[W.msn.rt.cur];
  unsigned nextPhase=W.msn.rt.phase==0?next->intro:next->main;
  if(nextPhase!=MSN_NONE16){const MsnPhase *np=&W.msn.f.phases[nextPhase];
   for(unsigned k=0;k<np->setup_count;k++){const MsnCmd *cmd=&W.msn.f.cmds[np->setup_first+k];if(cmd->op==MSN_OP_USEPEDGROUP)after=msn_arg_i(&W.msn.f,cmd,0);}}
  check("real-abort-replays-authored-intro",t->missionPedGroup==after&&t->group==(after>=0?after:t->zoneGroup));
 }
 printf("RESULT commands=%d groups=%u actualstarts=%d failures=%d\n",seen,groups,actualStarts,bad);return bad?1:0;
}
