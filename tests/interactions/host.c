// Real level collision/prop data, no PSP calls. Assert visible state changes, not log text.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"
#include "homer.h"
static Props props; static StateProps sp; static ColWorld world; static Car car;
static int fails, kicks, target, seenMode; static float seenX;
static void check(const char *name, int ok) { printf("%s %s\n",ok?"OK":"FAIL",name); fails+=!ok; }
#ifdef GLASS_NO_BREAK
static int kick(void *u,unsigned i,float dx,float dz) { (void)u;(void)dx;(void)dz; if ((int)i==target) kicks++; return 0; }
#else
static int kick(void *u,unsigned i,float dx,float dz) { (void)u;(void)dx;(void)dz; if ((int)i==target) kicks++; return 1; }
#endif
static int seen(void *u,float x,float y,float z,float r) { (void)u;(void)y;(void)z;(void)r;return seenMode==1||(seenMode==2&&fabsf(x-seenX)<.01f); }
static void put(float x,float y,float z,float nx,float nz) {
  car.x=x;car.y=y;car.z=z;car.h=atan2f(nx,nz);
  car.q[0]=cosf(car.h*.5f);car.q[1]=car.q[3]=0;car.q[2]=sinf(car.h*.5f);
  CarBox b={0};carBox(&car,&b);car.x+=x-b.x;car.z+=z-b.z;car.y+=y-(b.y+.5f*(b.lo+b.hi));
  car.vel[0]=nx*30;car.vel[1]=0;car.vel[2]=nz*30;car.v=30;
  propsUpdate(&props,&world,&car,1.f/60.f);
}
static void respawn(float ex,float ez,int frames) {
  for(int n=0;n<frames;n++)propsRespawnStep(&props,ex,ez,.05f,seen,0);
}
int main(int argc,char **argv) {
  if(argc!=3)return 2;
  FILE *f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);
  unsigned char *data=aligned_alloc(16,(size+15)&~15);if(!data||fread(data,1,size,f)!=(size_t)size)return 2;fclose(f);
  unsigned co=*(unsigned*)(data+92),po=*(unsigned*)(data+96),pv=*(unsigned*)(data+88),ce=(unsigned)size;
  if(po>co&&po<ce)ce=po;if(pv>co&&pv<ce)ce=pv;
  if(colInit(&world,data+co,ce-co)||propsInit(&props,data+po,*(unsigned*)(data+po+40))||spInit(&sp,props.spr,props.sprSize))return 2;
  const float *hd=(const float*)(data+12);carInit(&car,0,&world,hd[6],hd[7],hd[8],hd[9]);props.onKick=kick;
  int glass=0, cases=0, broken=0, early=0, misses=0, tunnelling=0;unsigned first=0;
  for(unsigned i=0;i<props.ninst;i++) {
    int pa,br;propsTypeFx(&props,props.def[i].type,&pa,&br);if(br!=19)continue;
    if(!glass)first=i;glass++;target=(int)i;PropState initial=props.st[i];
    float qx=initial.q[1],qy=initial.q[2],qz=initial.q[3],qw=initial.q[0];
    float nx=2*(qx*qz+qw*qy),nz=1-2*(qx*qx+qy*qy),len=hypotf(nx,nz);nx/=len;nz/=len;
    for(int dir=-1;dir<=1;dir+=2)for(int side=-1;side<=1;side++) {
      props.st[i]=initial;props.havePreviousCar=0;kicks=0;float contact=99;
      for(float d=-9;d<=9&&!kicks;d+=.25f) {
        put(initial.x+nx*d*dir+nz*side*4,initial.y,initial.z+nz*d*dir-nx*side*4,nx*dir,nz*dir);
        if(kicks)contact=fabsf(d);
      }
      cases++;broken+=kicks==1&&props.st[i].hidden;early+=kicks&&contact>car.p.halfL+initial.hz+.02f;
    }
    // Entire pane crossed between frames; the history must detect the contact.
    props.st[i]=initial;props.havePreviousCar=0;kicks=0;
    put(initial.x-nx*4,initial.y,initial.z-nz*4,nx,nz);
    put(initial.x+nx*4,initial.y,initial.z+nz*4,nx,nz);tunnelling+=kicks==1;
    // Parallel to the pane, two metres in front; under it; beyond its side edge.
    for(int mode=0;mode<3;mode++) {
      props.st[i]=initial;props.havePreviousCar=0;kicks=0;
      for(float d=-9;d<=9;d+=.5f) {
        float along=mode==0?2:d,side=mode==0?d:mode==2?initial.hx+car.p.halfW+1:0;
        put(initial.x+nx*along+nz*side,initial.y-(mode==1?initial.hy+3:0),initial.z+nz*along-nx*side,
            mode==0?nz:nx,mode==0?-nx:nz);
      }
      misses+=kicks!=0;
    }
    props.st[i]=initial;
  }
  printf("glass=%d contacts=%d/%d early=%d swept=%d/%d false_hits=%d\n",glass,broken,cases,early,tunnelling,glass,misses);
  // Правка Роба 71 (повтор 01.10, «не могу поехать налево и разбить стекло»): настоящий проезд, не телепорт. Машина с
  // разгона 10 и 30 м до стекла (12, 20, 28 м/с, газ; с трамплина перед стеклом — прыжок), с обеих сторон, car.c + propsUpdate 3 с. Где машина
  // пересекла плоскость стекла в его пределах — стекло обязано разбиться (VEHICLE_HIT -> обломок), скорость на стекле
  // теряется не больше 10 %; каждое из 13 стёкол разбивается хотя бы одним проездом. Отрицательный контроль: onKick,
  // возвращающий 0 (стекло без обломка, -DGLASS_NO_BREAK), — стекло цело, гейт обязан упасть.
  int drives=0,through=0,intact=0,slowed=0,panesBroken=0,panesReached=0;
  for(unsigned i=0;i<props.ninst;i++) {
    int pa,br;propsTypeFx(&props,props.def[i].type,&pa,&br);if(br!=19)continue;
    PropState initial=props.st[i];target=(int)i;int paneOk=0,reached=0;
    float qx=initial.q[1],qy=initial.q[2],qz=initial.q[3],qw=initial.q[0];
    float nx=2*(qx*qz+qw*qy),nz=1-2*(qx*qx+qy*qy),len=hypotf(nx,nz);nx/=len;nz/=len;
    for(int dir=-1;dir<=1;dir+=2)for(int si=0;si<6;si++){
      props.st[i]=initial;props.havePreviousCar=0;kicks=0;
      float dx=nx*dir,dz=nz*dir,sp=12.f+8.f*(si%3),run=si<3?10.f:30.f;
      carInit(&car,0,&world,initial.x-dx*run,initial.y+1.f,initial.z-dz*run,atan2f(dx,dz));carSetSpeed(&car,sp);
      CarInput in={1,0,0,0};float prevD=-1e9f,vBefore=0,vAfter=-1;int crossed=0;
      for(int n=0;n<180;n++){
        float v0=hypotf(car.vel[0],car.vel[2]);
        carUpdate(&car,&world,&in,1.f/60.f);propsUpdate(&props,&world,&car,1.f/60.f);
        float d=(car.x-initial.x)*dx+(car.z-initial.z)*dz,lat=fabsf((car.x-initial.x)*-dz+(car.z-initial.z)*dx);
        if(prevD<0.f&&d>=0.f&&lat<initial.hx&&car.y<initial.y+initial.hy&&car.y+1.6f>initial.y-initial.hy){crossed=1;vBefore=v0;}
        if(crossed&&vAfter<0.f&&d>2.f)vAfter=hypotf(car.vel[0],car.vel[2]);
        prevD=d;
      }
      if(!crossed)continue;
      drives++;int ok=kicks==1&&props.st[i].hidden;through+=ok;intact+=!ok;
      if(vAfter>=0.f&&vAfter<vBefore*.9f-.5f)slowed++;
      paneOk|=ok;reached=1;
    }
    if(!paneOk)printf("  pane %u (%.1f %.1f %.1f) n %.2f %.2f: %s\n",i,initial.x,initial.y,initial.z,nx,nz,
                      reached?"crossed but NOT broken":"not reached by a straight run-up (own route, e.g. from a ramp elsewhere)");
    panesBroken+=paneOk;panesReached+=reached;props.st[i]=initial;
  }
  printf("glass drive-through: %d crossings, broken %d, intact %d, slowed>10%% %d, panes reached %d, broken by driving %d/%d\n",drives,through,intact,slowed,panesReached,panesBroken,glass);
  check("driving through a pane breaks it",drives>0&&intact==0);
  check("pane does not stop the car",slowed==0);
  check("every reached pane is broken by driving into it (12+ of 13 reached)",panesBroken==panesReached&&panesReached>=12);
  check("13 source panes",glass==13);check("all directions and offsets break on contact",broken==cases&&early==0);
  check("fast sweep cannot skip a pane",tunnelling==glass);check("parallel/under/outside miss",misses==0);
  target=first;PropState original=props.st[first],*s=&props.st[first];float ex=s->x+1000,ez=s->z;
  s->hidden=1;seenMode=0;respawn(ex,ez,60);check("no respawn before five seconds",s->hidden);
  respawn(ex,ez,42);check("respawn restores original pose",!s->hidden&&s->asleep&&s->fresh&&s->x==original.x&&s->y==original.y);
  s->hidden=1;seenMode=1;respawn(ex,ez,150);check("visible pane stays destroyed",s->hidden);
  seenMode=0;respawn(s->home[0],s->home[2],150);check("nearby pane stays destroyed",s->hidden);
  s->noRespawn=1;respawn(ex,ez,150);check("mission ownership blocks respawn",s->hidden);s->noRespawn=0;
  s->x+=70;seenX=s->x;seenMode=2;respawn(ex,ez,150);check("visible displaced object stays in place",s->hidden&&s->x==seenX);
  seenMode=0;respawn(ex,ez,102);check("displaced object returns home",!s->hidden&&s->x==original.x);
  int ordinary=-1,mission=-1;
  for(unsigned i=0;i<sp.ninst;i++) {
    const SpType *t=&sp.type[sp.inst[i].type];
    if(sp.inst[i].tag&&t->nState>1)mission=i;
    if(!t->kind&&t->cls!=2&&!sp.inst[i].tag&&t->nState>1&&!sp.state[t->firstState].nCall)ordinary=i;
  }
  check("ordinary and mission stateprop fixtures exist",ordinary>=0&&mission>=0);
  if(ordinary>=0&&mission>=0) {
    sp.run[ordinary].state=sp.run[mission].state=1;sp.run[ordinary].alive=sp.run[mission].alive=0;
    for(int n=0;n<102;n++)spRespawnStep(&sp,10000,10000,.05f,seen,0);
    check("ordinary stateprop respawns with collision",sp.run[ordinary].state==0&&sp.run[ordinary].alive&&sp.run[ordinary].colOn);
    check("mission stateprop never respawns implicitly",sp.run[mission].state==1&&!sp.run[mission].alive);
    sp.run[ordinary].noRespawn=1;sp.run[ordinary].alive=0;
    for(int n=0;n<102;n++)spRespawnStep(&sp,10000,10000,.05f,seen,0);
    check("stateprop ownership blocks respawn",!sp.run[ordinary].alive);
  }
  // правка 334: разовый стейтпроп (с монетами в машине состояний, stateprops.h spOnce) не возвращается вне вида; прежнее поведение
  // (spOnceOld = 1) — возвращается: контроль, что проверка умеет падать
  { int once=-1; for(unsigned i=0;i<sp.ninst&&once<0;i++) if(spOnce(&sp,i)&&sp.type[sp.inst[i].type].nState>1) once=(int)i;
    check("coin stateprop fixture exists",once>=0);
    if(once>=0) {
      sp.run[once].state=1;sp.run[once].alive=0;sp.run[once].noRespawn=0;
      for(int n=0;n<102;n++)spRespawnStep(&sp,10000,10000,.05f,seen,0);
      check("coin stateprop never respawns",sp.run[once].state==1&&!sp.run[once].alive);
      spOnceOld=1;for(int n=0;n<102;n++)spRespawnStep(&sp,10000,10000,.05f,seen,0);spOnceOld=SP_ONCE_OLD;
      check("old rule (control) respawns coin stateprop",sp.run[once].state==0&&sp.run[once].alive);
    }
  }
  carInit(&car,0,&world,hd[6],hd[7],hd[8],hd[9]);float x=car.x,z=car.z;
  car.nsafe=1;car.safeHead=2;car.safe[2].x=x;car.safe[2].y=car.y;car.safe[2].z=z;car.safe[2].h=car.h;
  car.damage=.6f;car.x+=50;carResetNearby(&car,&world);
  check("reset uses and consumes latest safe position",hypotf(car.x-x,car.z-z)<.05f&&car.nsafe==0&&car.safeHead==1);
  check("reset preserves damage",fabsf(car.damage-.6f)<.001f);
  car.homeX+=500;car.homeZ+=500;x=car.x;z=car.z;carResetNearby(&car,&world);
  check("empty history resets in place, not level spawn",hypotf(car.x-x,car.z-z)<.1f);
  SkinModel *m=skinLoad(argv[2]);static Homer h;if(!m||homerInit(&h,m))return 2;HomerCar hc;homerCarFrom(&hc,&car,.62f);
  int entered=0;
  for(int side=0;side<4;side++) {
    float nx=side<2?hc.box.fx:-hc.box.fz,nz=side<2?hc.box.fz:hc.box.fx,sgn=side%2?1:-1;
    float distance=(side<2?hc.box.hl:hc.box.hw)+3.2f;
    homerPlace(&h,&world,hc.box.x+nx*distance*sgn,car.y+1,hc.box.z+nz*distance*sgn,car.h);
    h.y=hc.m[13]-hc.lift;h.grounded=1;
    if(homerCanEnter(&h,&hc)&&homerEnterCar(&h,&hc,0)) {
      for(int n=0;n<600&&h.state!=HS_IN_CAR;n++)homerUpdate(&h,&world,&hc,0,1.f/60.f);
      entered+=h.state==HS_IN_CAR;
    }
  }
  check("entry from all four sides at 3.2m",entered==4);
  h.state=HS_FOOT;h.x=hc.box.x;h.z=hc.box.z;h.y=hc.m[13]-hc.lift;h.grounded=0;
  check("entry request accepted while briefly airborne",homerCanEnter(&h,&hc));h.state=HS_KICK;
  check("entry request accepted after kick",homerCanEnter(&h,&hc));h.y+=4;
  check("entry from another height rejected",!homerCanEnter(&h,&hc));
  h.y-=4;h.x+=30;check("distant entry rejected",!homerCanEnter(&h,&hc));
  printf("RESULT: %s (%d failures)\n",fails?"FAIL":"OK",fails);
  skinFree(m);spFree(&sp);propsFree(&props);free(data);return fails?1:0;
}
