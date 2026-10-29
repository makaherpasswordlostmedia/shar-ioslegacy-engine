/* №512: картинка брифинга при старте сразу в основную фазу (Retry после провала, restore, продолжение): вступление (sd) не идёт, а картинка стоит в его скрипте.
   Для каждой миссии пакета MSN1 — какая картинка пришла к моменту вызова mission_title. Красный контроль: -DBRIEFPIC_512_OLD=1. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mission/msn_game.h"
static char bitmap[160], atTitle[160]; static int titles;
static void present(void *u,const char *path){(void)u;snprintf(bitmap,sizeof bitmap,"%s",path?path:"");}
static void title(void *u,const char *id,const char *t,const char *info,int bonus){(void)u;(void)id;(void)t;(void)info;(void)bonus;titles++;snprintf(atTitle,sizeof atTitle,"%s",bitmap);}
int main(int argc,char **argv) {
 if(argc!=2)return 2;
 FILE *fd=fopen(argv[1],"rb");if(!fd)return 2;fseek(fd,0,SEEK_END);long size=ftell(fd);rewind(fd);
 void *data=malloc(size);if(fread(data,1,size,fd)!=(size_t)size)return 2;fclose(fd);MsnFile f;char err[200];
 if(msn_open(&f,data,size,err,sizeof err)){fprintf(stderr,"FAIL %s\n",err);return 2;}
 for(unsigned mi=0;mi<f.nmissions;mi++) {
  const MsnMission *m=&f.missions[mi];MsnRuntime rt;MsnGame mg;MsnGameApi api;memset(&api,0,sizeof api);
  api.ui.presentation=present;api.ui.mission_title=title;bitmap[0]=atTitle[0]=0;titles=0;
  msn_game_init(&mg,&rt,&f,&api);msn_start_mission(&rt,mi,0);   /* вступление идёт: обычный старт */
  char normal[160];snprintf(normal,sizeof normal,"%s",atTitle[0]?atTitle:"-");
  bitmap[0]=atTitle[0]=0;titles=0;
  msn_game_init(&mg,&rt,&f,&api);rt.cp_phase=1;rt.cp_stage=0;msn_start_mission(&rt,mi,1);   /* сразу основная фаза */
  printf("CASE %u %s %u titles=%d normal=%s restore=%s\n",mi,msn_str(&f,m->id),m->flags,titles,normal,atTitle[0]?atTitle:"-");
 }
 free(data);return 0;
}
