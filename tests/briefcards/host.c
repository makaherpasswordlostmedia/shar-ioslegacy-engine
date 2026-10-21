/* Real mission UI callback dispatch, every mission in a supplied MSN1 package.
   Objective success is injected to enter subsequent intro stages; this is image selection, not mission traversal. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mission/msn_game.h"
static char bitmap[160]; static int titles;
static void present(void *u,const char *path){(void)u;snprintf(bitmap,sizeof bitmap,"%s",path?path:"");}
static void title(void *u,const char *id,const char *t,const char *info,int bonus){(void)u;(void)id;(void)t;(void)info;(void)bonus;titles++;}
int main(int argc,char **argv) {
 if(argc!=2)return 2;
 FILE *fd=fopen(argv[1],"rb");if(!fd)return 2;fseek(fd,0,SEEK_END);long size=ftell(fd);rewind(fd);
 void *data=malloc(size);fread(data,1,size,fd);fclose(fd);MsnFile f;char err[200];
 if(msn_open(&f,data,size,err,sizeof err)){fprintf(stderr,"FAIL %s\n",err);return 2;}
 for(unsigned mi=0;mi<f.nmissions;mi++) {
  const MsnMission *m=&f.missions[mi];MsnRuntime rt;MsnGame mg;MsnGameApi api;memset(&api,0,sizeof api);
  api.ui.presentation=present;api.ui.mission_title=title;bitmap[0]=0;titles=0;
  msn_game_init(&mg,&rt,&f,&api);msn_start_mission(&rt,mi,0);
  for(int n=0;rt.phase==0 && n<100;n++) {
   rt.status=MSN_BETWEEN;rt.delay=0;MsnWorld w;memset(&w,0,sizeof w);msn_tick(&rt,.01f,&w);
  }
  printf("CASE %u %s %u %d %s\n",mi,msn_str(&f,m->id),m->flags,titles,bitmap[0]?bitmap:"-");
 }
 free(data);return 0;
}
