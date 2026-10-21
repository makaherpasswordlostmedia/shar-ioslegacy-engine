// Bound cargo is dropped AT the last-passed waypoint, including the final one.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mission/msn.h"
static int passed,drop[MSN_MAX_ITEMS],checks,bad,stages;
static int entity(void *u,const char *n,MsnEntity *e){(void)u;(void)n;*e=(MsnEntity){.pos={10,2,10},.health=1,.finished=0,.waypoint=passed};return 1;}
static void event(void *u,const MsnEvent *e){(void)u;if(e->type==MSN_EV_DROP&&e->index>=0&&e->index<MSN_MAX_ITEMS)drop[e->index]++;}
static void check(int ok,const char *msg){checks++;if(!ok){bad++;printf("FAIL %s\n",msg);}}
int main(int argc,char **argv){
 if(argc<2)return 2;
 for(int arg=1;arg<argc;arg++){
  FILE *f=fopen(argv[arg],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);void *data=malloc(n);if(!data)return 2;
  if(fread(data,1,n,f)!=(size_t)n)return 2;fclose(f);MsnFile F;char err[160];if(msn_open(&F,data,n,err,sizeof err)){puts(err);return 2;}
  MsnHost host={.entity=entity,.event=event};MsnWorld w={.player={30,2,10},.vehicle_health=1,.vehicle="player"};
  for(unsigned mi=0;mi<F.nmissions;mi++)for(int phase=0;phase<2;phase++){
   unsigned pi=phase?F.missions[mi].main:F.missions[mi].intro;if(pi==MSN_NONE16)continue;const MsnPhase *ph=&F.phases[pi];
   for(int si=0;si<ph->stage_count;si++){
    MsnRuntime rt;passed=-1;msn_init(&rt,&F,&host);rt.cp_phase=phase;rt.cp_stage=si;msn_start_mission(&rt,mi,1);
    if(!rt.st||rt.obj!=MSN_OBJ_DUMP||!rt.nbind)continue;
    stages++;rt.remaining=100000;memset(drop,0,sizeof drop);
    for(int t=0;rt.status==MSN_COUNTDOWN&&t<2000;t++)msn_tick(&rt,.01f,&w);
    check(rt.status==MSN_RUNNING,"authored countdown enters the objective");int max=0;
    for(int b=0;b<rt.nbind;b++)if(rt.bind_wp[b]>max)max=rt.bind_wp[b];
    for(passed=-1;passed<=max;passed++)for(int repeat=0;repeat<3;repeat++){
     msn_tick(&rt,.01f,&w);
     for(int b=0;b<rt.nbind;b++){
      int it=rt.bind_item[b],expected=passed>=rt.bind_wp[b];
      check(rt.released[it]==expected,"release at the authored waypoint");
      check(drop[it]==expected,"one drop event per item, including final waypoint");
      if(expected)check(rt.relpos[it].x==10&&rt.relpos[it].z==10,"drop occurs at the live target position");
     }
    }
   }
  }
  free(data);
 }
 check(stages==5,"five disc-authored bound cargo stages exercised");
 printf("%s bound cargo stages=%d checks=%d failures=%d\n",bad?"FAIL":"PASS",stages,checks,bad);return !!bad;
}
