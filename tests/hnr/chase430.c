// 430: production police driver must close on stationary and moving players.
// Flat calibration isolates pursuit intent from road blockers in the recorded PS2 scene.
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "game_msn.h"
#include "car.h"
#include "msncar.h"
#include "chase430_ref.h"
static struct { ColHdr h; ColTri t[2]; unsigned starts[2], refs[2]; } floorData;
int main(int argc,char **argv) {
  if(argc!=8)return 2;
  memcpy(floorData.h.magic,"COL1",4);
  floorData.h.ox=floorData.h.oz=-512; floorData.h.cell=1024;
  floorData.h.W=floorData.h.H=1; floorData.h.ntri=floorData.h.nref=2;
  floorData.t[0]=(ColTri){{-512,0,-512},{512,0,512},{512,0,-512},{0,1,0}};
  floorData.t[1]=(ColTri){{-512,0,-512},{-512,0,512},{512,0,512},{0,1,0}};
  floorData.starts[1]=2; floorData.refs[1]=1;
  ColWorld world; if(colInit(&world,&floorData,sizeof floorData))return 2;
  int fail=0;
  for(int level=1;level<=7;level++) {
    FILE *file=fopen(argv[level],"rb");if(!file)return 2;
    fseek(file,0,SEEK_END);long size=ftell(file);rewind(file);void *blob=malloc(size);
    if(!blob||fread(blob,1,size,file)!=(size_t)size)return 2;fclose(file);
    MsnFile pack;char err[256];if(msn_open(&pack,blob,size,err,sizeof err))return 2;
    GameHnrConfig config=gameMsnHnrConfig(&pack);
    for(int moving=0;moving<2;moving++) {
    Car player; carInit(&player,0,&world,0,0,0,0);
    MsnCars cars; mcInit(&cars);
    float p[3]={0,0,-PS2_430_START};
    McCar *cop=mcSpawn(&cars,&world,0,config.car,p,0,1,"chase",config.con,"");
    if(!cop)return 2; cop->police=1;
    double best=PS2_430_START, at1=0;
    for(int n=0;n<360;n++) {
      if(moving) { CarInput input={.4f,0,0,0}; carUpdate(&player,&world,&input,1.f/60.f); }
      McEnv env={0}; env.w=&world; env.player=&player; env.driving=1;
      env.ppos[0]=player.x;env.ppos[1]=player.y;env.ppos[2]=player.z;
      mcUpdate(&cars,&env,1.f/60.f,0,0);
      double d=hypot(cop->car.x-player.x,cop->car.z-player.z);
      if(!isfinite(d)){colFree(&world);return 2;}
      if(d<best)best=d;if(n==59)at1=d;
    }
    double closed=PS2_430_START-best;
    int good=closed>=PS2_430_CLOSED && at1<PS2_430_START;
    printf("L%d %s %s %s: start=%.3f at1=%.3f nearest6=%.3f closed=%.3f PS2_closed=%.3f\n",level,config.car,good?"PASS":"FAIL",moving?"moving":"standing",PS2_430_START,at1,best,closed,PS2_430_CLOSED);
    fail+=!good;
    }
    free(blob);
  }
  colFree(&world);return fail?1:0;
}
