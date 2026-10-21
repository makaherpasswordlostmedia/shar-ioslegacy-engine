/* Disc-authored pool/decay through the actual common runtime. No PSP oracle timings invented. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W; static int bad;
static void check(const char *name,int pass){printf("CHECK %s %s\n",name,pass?"PASS":"FAIL");bad+=!pass;}
static int pool(void){int n=0;for(int i=0;i<W.msn.cars.n;i++) if(W.msn.cars.c[i].on&&!strcasecmp(W.msn.cars.c[i].name,W.msn.hnr.car))n++;return n;}
int main(int argc,char **argv){
 if(argc!=9)return 2;setvbuf(stdout,0,_IONBF,0);
 if(bwData(argv[1],argv[2],argv[3]))return 2;
 bwNew(&W);for(int i=0;i<30;i++)bwStep(&W,0,0,0);
 int count=atoi(argv[6]);float decay=atof(argv[7]);
 check("model",!strcmp(W.msn.hnr.car,argv[4]));check("con",!strcmp(W.msn.hnr.con,argv[5]));
 check("population-command",W.msn.hnr.count==count);check("decay-command",fabsf(W.msn.hnr.decay-decay)<.001f);
 gameMsnHnrPolice(&W.msn,1);check("population-runtime",pool()==count);
 for(int i=0;i<W.msn.cars.n;i++)if(W.msn.cars.c[i].on&&!strcasecmp(W.msn.cars.c[i].name,W.msn.hnr.car)) {
  McCar *c=&W.msn.cars.c[i];check("original-con",!strcmp(c->con,argv[5])&&c->conOk);
  check("model-geometry",c->geoOk);check("spawn-distance",hypotf(c->car.x-(gameOnFoot(&W.G)?W.homer.x:W.car.x),c->car.z-(gameOnFoot(&W.G)?W.homer.z:W.car.z))>=89.99f);
 }
 // Repeat through actual remove/spawn; no retained duplicate or lost second car.
 gameMsnHnrPolice(&W.msn,0);check("remove-all",pool()==0);
 gameMsnHnrPolice(&W.msn,1);check("respawn-population",pool()==count);
 W.hnrHeat=.5f;W.hnrCalm=3;W.G.hnrLatched=0;W.G.hnrRoom=0;
 for(int i=0;i<120;i++)gameHnrRate(&W.G,1.f/60.f,W.msn.hnr.decay);
 check("decay-runtime",fabsf(W.hnrHeat-(.5f-decay*.02f))<.002f);
 // Real car collision -> mcUpdate callback -> HNR, including the authored L7 hearse.
 gameMsnHnrPolice(&W.msn,0);gameMsnHnrPolice(&W.msn,1);
 McCar *target=mcFind(&W.msn.cars,W.msn.hnr.car);
 if(target) {
  for(int i=0;i<W.msn.cars.n;i++) if(&W.msn.cars.c[i]!=target)W.msn.cars.c[i].on=0;
  float x=target->car.x,z=target->car.z,y=target->car.y;
  carPlace(&target->car,W.G.pWorld,x,y,z,0.f);target->mode=MC_PARKED;target->asleep=1;
  bwPlace(&W,x-3.f,y,z,1.5707963f);carSetSpeed(&W.car,20.f);
  W.hnrHeat=0;W.hnrCalm=3;W.G.hnrLatched=1;W.G.hnrOff=0;W.G.hnrRoom=0;W.G.hnrBusted=0;
  unsigned before=W.msn.cars.hits;GamePad pad;memset(&pad,0,sizeof pad);
  gameMsnTick(&W.msn,&pad,1.f/60.f);
  printf("IMPACT model=%s callbacks=%u speed=%.3f heat=%.3f\n",target->name,W.msn.cars.hits-before,W.car.hitSpeed,W.hnrHeat*100);
  check("collision-observed",W.msn.cars.hits>before&&W.car.hitSpeed>1.f);
  check("police-hit-heat",fabsf(W.hnrHeat-.05f)<.001f);
 } else check("collision-target",0);
 printf("RESULT %s failures=%d\n",bad?"FAIL":"PASS",bad);return !!bad;
}
