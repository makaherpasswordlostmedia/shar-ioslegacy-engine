/* Actual level COL1/CAR1/wrench -> repair -> fresh HomerCar -> gameTriangle -> seated,
   then an actual NPC TRF model against this repaired player car. No production mutation. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"
#include "traffic.h"
static BotWorld B;static int fails,checks;
static void ck(const char*n,int v){checks++;fails+=!v;printf("CHECK %s %s\n",n,v?"PASS":"FAIL");}
static void nearDoor(HomerCar *hc){
 homerCarFrom(hc,&B.car,B.lift);
 float x=hc->m[12]+hc->m[0]*hc->door[0]-hc->m[4]*hc->lift+hc->m[8]*hc->door[1];
 float y=hc->m[13]+hc->m[1]*hc->door[0]-hc->m[5]*hc->lift+hc->m[9]*hc->door[1];
 float z=hc->m[14]+hc->m[2]*hc->door[0]-hc->m[6]*hc->lift+hc->m[10]*hc->door[1];
 homerPlace(&B.homer,bwCol(),x,y,z,B.car.h);
 printf("DOOR car=%.2f,%.2f,%.2f H=%.2f,%.2f,%.2f ytarget=%.2f dead=%d husk=%d state=%d\n",B.car.x,B.car.y,B.car.z,B.homer.x,B.homer.y,B.homer.z,y,hc->dead,hc->husk,B.homer.state);
}
int main(int argc,char**argv){
 if(argc!=5)return 2;setvbuf(stdout,0,_IONBF,0);int red=atoi(argv[4]);
 if(bwData(argv[1],argv[2],argv[3])||bwNew(&B))return 2;
 const ColWorld *w=bwCol();const Traffic *src=bwTraffic();Game*g=&B.G;
 ck("authored-car",bwCarSource()==1);ck("authored-wrenches",w->nwrench>0);ck("authored-NPC-models",src&&src->hd&&src->hd->nModel>0);
 if(!w->nwrench||!src)return 2;
 const ColWrench*k=&w->wrench[0];
 /* Keep the authored car spawn; an arbitrary point beside a wrench is not a
    supported car parking fixture. Other slopes/decks remain outside this gate. */
 B.car.damage=1;B.car.destroyed=1;B.wasDestroyed=1;
 const Car *identity=g->pCar;char name[32];snprintf(name,sizeof name,"%s",B.car.p.name);
 CarInput in={0,0,0,1};for(int i=0;i<150;i++)gameCarStep(g,&in,1.f/60);
 HomerCar hc;memset(&hc,0,sizeof hc);nearDoor(&hc);
 ck("burning-denies-entry",!carBoomed(&B.car)&&hc.dead&&!homerCanEnter(&B.homer,&hc));
 for(int i=0;i<70;i++)gameCarStep(g,&in,1.f/60);
 ck("actual-boom",carBoomed(&B.car));
 gameWrenchStep(g);unsigned repairs=g->wrenchRepairs;homerPlace(&B.homer,w,k->p[0],k->p[1]-.8f,k->p[2],0);
 int got=gameWrenchStep(g);
 /* RED consumes the real action result but restores the stale destroyed state, to prove the
    gate observes repair/entry rather than merely the pickup counter. This is a broken fixture. */
 if(red==1){B.car.damage=1;B.car.destroyed=1;B.wasDestroyed=1;}
 ck("wrench-action",got>0&&(g->wrenchTaken&1)&&g->wrenchRepairs==repairs+1);
 ck("repaired-state",!B.car.destroyed&&!B.car.damage&&!B.wasDestroyed&&!carBoomed(&B.car));
 ck("same-primary-car",identity==g->pCar&&!strcmp(name,B.car.p.name));
 ck("wrench-hidden",g->wrenchInst[0]>=0&&!B.sp.run[g->wrenchInst[0]].alive);
 nearDoor(&hc);ck("fresh-entry-allowed",!hc.dead&&!hc.husk&&homerCanEnter(&B.homer,&hc));
 gameTriangle(g);GamePad pad={0};for(int i=0;i<180;i++)gameAfterCar(g,&pad,1.f/60);
 ck("triangle-actually-seated",homerDriving(&B.homer));
 static Traffic t;t=*src;t.maxCars=1;t.npark=0;t.noSolid=red==2;
 memset(t.car,0,sizeof t.car);TrCar*c=&t.car[0];c->mode=TRM_DRIVE;c->model=0;
 carInit(&c->car,&src->params[0],w,B.car.x+1.2f,B.car.y,B.car.z,0);
 float before=hypotf(c->car.x-B.car.x,c->car.z-B.car.z);Car keep=B.car;
 int hits=trafficHitStill(&t,w,&B.car);float after=hypotf(c->car.x-B.car.x,c->car.z-B.car.z);
 printf("MEASURE level=%d player=%s NPC=%s wrench=%u hit=%d separation=%.3f/%.3f seated=%d repair=%u\n",bwLevel(),name,c->car.p.name,w->nwrench,hits,before,after,homerDriving(&B.homer),g->wrenchRepairs);
 ck("NPC-solid-after-repair",hits>0&&after>before+.05f&&c->mode==TRM_PHYS&&B.car.x==keep.x&&B.car.z==keep.z);
 printf("RESULT %s checks=%d failures=%d\n",fails?"FAIL":"PASS",checks,fails);return !!fails;
}
