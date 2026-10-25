// Native swarm: reuse cartest's loader/road bots and the exact PSP car/col modules.
// One world per process: ColWorld scratch is deliberately never shared across threads.
#define main cartestLegacyMain
#include "cartest.c"
#undef main
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include "../../viewer/props.h"
#include "../../viewer/stateprops.h"

#ifndef FLEET
#define FLEET 1024
#endif
#define SEEDS 100000
#define COV 131072
typedef struct { float x,y,z; int layer,stacked; float nx,nz; } Start;
typedef struct {
  Car c; Bot b; uint32_t random;
  CarBox previous;
  int start, epoch, air, flags, prevGround, penTicks, wallTicks,scenario;
  float launchY, maxY, prevY, lastX,lastZ;
} Driver;
static Driver fleet[FLEET]; static int fleetN=64, tick, startsN, layeredN;
static Start starts[SEEDS];
static uint64_t cells[COV]; static unsigned covered;
static unsigned long hits, jumps, landings, transitions, bounces, suspicions, updates;
static int speed=1, paused, stopping, fatal, episodeTicks=1800;
static uint32_t campaignSeed=7;
static double began;
static double cpuNow(void){struct timespec t;clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&t);return t.tv_sec+t.tv_nsec*1e-9;}
unsigned homerSolidFrame;   // homer.c в рой не входит; 0 = «вне homerUpdate», кеш соседей props.c выключен (как в прежних тестах)
static Props objects;static StateProps stateObjects;
static unsigned char *glassVisited;static int contactCar,glassTotal,glassCovered;
static unsigned long propImpacts,glassBreaks,stateHits;

static int sane(const Car *c) {
  const float v[]={c->x,c->y,c->z,c->vel[0],c->vel[1],c->vel[2],c->q[0],c->q[1],c->q[2],c->q[3],c->pen,c->damage};
  for(unsigned i=0;i<sizeof v/sizeof *v;i++) if(!isfinite(v[i]) || fabsf(v[i])>1e7f) return 0;
  return 1;
}
static void coverage(float x,float y,float z) {
  // Actual occupied XYZ voxels, not a 2D reachability promise; collisions resolved exactly.
  int32_t q[3]={(int32_t)floorf(x/4),(int32_t)floorf(y/2),(int32_t)floorf(z/4)};
  uint64_t h=1469598103934665603ULL;
  for(int k=0;k<3;k++){ h^=(uint32_t)q[k];h*=1099511628211ULL; }
  h|=1; unsigned at=(unsigned)h&(COV-1);
  for(unsigned n=0;n<COV;n++,at=(at+1)&(COV-1)){
    if(cells[at]==h)return;
    if(!cells[at]){cells[at]=h;covered++;return;}
  }
}
static void event(int id,const char *kind,int detail) {
  Car *c=&fleet[id].c;
  printf("{\"type\":\"event\",\"tick\":%d,\"car\":%d,\"kind\":\"%s\",\"detail\":%d,\"epoch\":%d,\"start\":%d,\"xyz\":[%.5f,%.5f,%.5f]}\n",
    tick,id,kind,detail,fleet[id].epoch,fleet[id].start,c->x,c->y,c->z);
}
static int kickObject(void *user,unsigned i,float dx,float dz){
  (void)user;(void)dx;(void)dz;propImpacts++;
  int part,br;propsTypeFx(&objects,objects.def[i].type,&part,&br);
  int bt=spBreakOf(&stateObjects,objects.def[i].type);if(bt<0)return 0;
  float pos[]={objects.def[i].x,objects.def[i].y,objects.def[i].z};
  int hidden=spBreak(&stateObjects,(unsigned)bt,pos,objects.def[i].q);
  if(hidden&&br==19){glassBreaks++;if(!glassVisited[i]){glassVisited[i]=1;glassCovered++;}event(contactCar,"glass",(int)i);}
  return hidden;
}
static void loadObjects(void){
  unsigned po=*(unsigned*)(file+96);if(!po||(uint64_t)po+64>fileSize){fprintf(stderr,"missing PRP2\n");exit(2);}
  unsigned size=*(unsigned*)(file+po+40);
  if((uint64_t)po+size>fileSize||propsInit(&objects,file+po,size)||spInit(&stateObjects,objects.spr,objects.sprSize)){fprintf(stderr,"invalid object data\n");exit(2);}
  if(!glassVisited)glassVisited=calloc(objects.ninst,1);if(!glassVisited)exit(2);
  glassTotal=0;
  for(unsigned i=0;i<objects.ninst;i++){int pa,br;propsTypeFx(&objects,objects.def[i].type,&pa,&br);if(br==19)glassTotal++;}
  objects.onKick=kickObject;
}
static void makeStarts(void) {
  // Enumerate stacked supports independently: ground below a roof is kept too.
  for(float z=W.oz+4;z<W.oz+W.H*W.cell;z+=8)
    for(float x=W.ox+4;x<W.ox+W.W*W.cell;x+=8){
      float top=10000,g;int first=startsN;
      for(int layer=0;layer<12;layer++){
        float n[3];if(!colGround(&W,x,z,top,-1000,&g,n))break;
        if(startsN==SEEDS){fprintf(stderr,"surface seed capacity exceeded\n");exit(2);}
        starts[startsN++]=(Start){x,g,z,layer,0,n[0],n[2]};
        if(layer)starts[first].stacked=1;
        if(layer)layeredN++;
        top=g-.12f;
      }
    }
  if(!startsN){fprintf(stderr,"zero support seeds\n");exit(2);}
}
static void spawn(int id,int epoch) {
  Driver *d=&fleet[id]; memset(d,0,sizeof *d);d->epoch=epoch;
  rng=campaignSeed^(0x9e3779b9u*(unsigned)(id+1))^(0x85ebca6bu*(unsigned)(epoch+1)); if(!rng)rng=1;
  for(int tries=0;tries<500;tries++){
    float x,y,z,h; int start=-1,road=-1,scenario=0;
    // Road fleets converge on shared segments, with opposing cars to exercise collisions.
    if(id%4!=3 && nroad){
      unsigned group=(unsigned)(id/4+epoch*17);
      road=(int)((group*109u+campaignSeed)%nroad); Road *r=&roads[road];
      float u=.25f+(id%4)*.2f;
      if(tries) {road=(int)(rnd()%(unsigned)nroad);r=&roads[road];u=.2f+.6f*frand();}
      x=r->ax+(r->bx-r->ax)*u; y=r->ay+(r->by-r->ay)*u;z=r->az+(r->bz-r->az)*u;
      h=atan2f(r->bx-r->ax,r->bz-r->az)+(id%4==1?PI:0);
    }else{
      start=(int)(rnd()%(unsigned)startsN);Start *s=&starts[start];
      int mode=(id/4+epoch)%4;
      if(tries<300 && mode!=3 && !s->stacked)continue;
      x=s->x;y=s->y;z=s->z;h=frand()*2*PI;
      scenario=mode==0?2:mode==1?3:mode==2?4:1;
      // A sloped support gets an uphill run; flat roof tests get deterministic launch/drop velocities.
      if(mode==3 && s->nx*s->nx+s->nz*s->nz>.015f){h=atan2f(-s->nx,-s->nz);scenario=5;}
    }
    const char *models[]={"famil_v","sportsa","pickupa","schoolbu"};CarParams p;
    if(!carParamsFor(models[id%4],&p)){fprintf(stderr,"missing vehicle parameters\n");exit(2);}
    carInit(&d->c,&p,&W,x,y,z,h);CarBox b;carBox(&d->c,&b);colProbeCar(&W,&b);
    if(!sane(&d->c)||b.maxDepth>.025f||!d->c.grounded||d->c.wheels<3||fabsf(d->c.y-y)>1.4f)continue;
    int overlap=0;
    for(int j=0;j<id;j++) if(fabsf(fleet[j].c.x-d->c.x)<4 && fabsf(fleet[j].c.z-d->c.z)<7 && fabsf(fleet[j].c.y-d->c.y)<3)overlap=1;
    if(overlap)continue;
    d->start=start;d->scenario=scenario;d->b.mode=scenario>=2?2:(road>=0 && id%4==0)?0:1;
    if(d->b.mode==0){d->b.cur=road;d->b.nxt=pickNext(road);}
    d->lastX=d->b.lastX=d->c.x;d->lastZ=d->b.lastZ=d->c.z;d->prevY=d->c.y;d->prevGround=1;
    d->random=rng; carSetSpeed(&d->c,scenario>=2?26.f:7.f+(id%3)*3.f);
    if(scenario==3){d->c.y+=2;d->c.vel[1]=8;d->c.grounded=0;}
    if(scenario==4){d->c.y+=8;d->c.vel[1]=-10;carSetSpeed(&d->c,3);d->c.grounded=0;}
    carBox(&d->c,&d->previous);return;
  }
  fprintf(stderr,"could not place car %d after 500 attempts\n",id);exit(2);
}
static void frame(void){
  printf("{\"type\":\"frame\",\"tick\":%d,\"seed\":%u,\"speed\":%d,\"paused\":%s,\"elapsed\":%.3f,\"updates\":%lu,\"hits\":%lu,\"jumps\":%lu,\"landings\":%lu,\"transitions\":%lu,\"bounces\":%lu,\"suspicions\":%lu,\"coverage\":%u,\"starts\":%d,\"layeredStarts\":%d,\"cars\":[",
    tick,campaignSeed,speed,paused?"true":"false",now()-began,updates,hits,jumps,landings,transitions,bounces,suspicions,covered,startsN,layeredN);
  for(int i=0;i<fleetN;i++){
    Driver *d=&fleet[i];Car *c=&d->c;
    printf("%s[%d,%.5f,%.5f,%.5f,%.6f,%.6f,%.6f,%.6f,%.3f,%d,%.4f,%d,%d,%d,%.2f,%.2f,%.2f,%.2f,%d]",
      i?",":"",i,c->x,c->y,c->z,c->q[0],c->q[1],c->q[2],c->q[3],c->v,d->flags,c->damage,d->epoch,d->start,c->revWhy,c->p.halfW,c->p.halfL,c->p.bodyLo,c->p.bodyHi,d->scenario);
  }
  printf("],\"cpuSeconds\":%.6f,\"propImpacts\":%lu,\"glassBreaks\":%lu,\"glassCovered\":%d,\"glassTotal\":%d,\"stateHits\":%lu,\"objects\":[",cpuNow(),propImpacts,glassBreaks,glassCovered,glassTotal,stateHits);
  for(unsigned i=0;i<objects.ninst;i++){
    PropState *s=&objects.st[i];int pa,br;propsTypeFx(&objects,objects.def[i].type,&pa,&br);
    printf("%s[%u,%.3f,%.3f,%.3f,%.5f,%.5f,%.5f,%.5f,%.3f,%.3f,%.3f,%d,%d]",i?",":"",i,s->x,s->y,s->z,s->q[0],s->q[1],s->q[2],s->q[3],s->hx,s->hy,s->hz,s->hidden,br==19);
  }
  printf("],\"states\":[");int ns=0;
  for(unsigned i=0;i<stateObjects.ninst;i++){
    SpRun *r=&stateObjects.run[i];const SpType *t=&stateObjects.type[stateObjects.inst[i].type];
    if(!r->alive||!r->colOn||t->kind)continue;float c[3],h[3];
    for(int k=0;k<3;k++){c[k]=r->R[k]*t->c[0]+r->R[3+k]*t->c[1]+r->R[6+k]*t->c[2];h[k]=fabsf(r->R[k])*t->h[0]+fabsf(r->R[3+k])*t->h[1]+fabsf(r->R[6+k])*t->h[2];}
    printf("%s[%u,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%u]",ns++?",":"",i,r->x+c[0],r->y+c[1],r->z+c[2],h[0],h[1],h[2],r->state);
  }
  puts("]}");fflush(stdout);
}
static int byX(const void *aa,const void *bb){
  int a=*(const int*)aa,b=*(const int*)bb;float x=fleet[a].c.x-fleet[b].c.x;
  return x<0?-1:x>0?1:a-b;
}
static int simulate(const char *inject){
  tick++;
  if(tick>1 && (tick-1)%episodeTicks==0){
    // A new independent trial, not a claim of in-game respawn around an observer.
    propsFree(&objects);spFree(&stateObjects);loadObjects();
  }
  propsAdvance(&objects,&W,1.f/60);spUpdate(&stateObjects,&W,0,0,1.f/60);stateObjects.nfx=0;
  for(int i=0;i<fleetN;i++){
    Driver *d=&fleet[i];Car *c=&d->c;
    if((tick-1)%episodeTicks==0 && tick>1)spawn(i,d->epoch+1);
    rng=d->random;CarInput in={0};botStep(&d->b,c,&in,(tick-1)%episodeTicks/60.f);d->random=rng;
    int rec=c->recoveries;unsigned fb=c->foliageBounces;
    carUpdate(c,&W,&in,1.f/60);updates++;
    if(inject && tick==30 && i==0 && !strcmp(inject,"nan"))c->vel[0]=NAN;
    if(!sane(c)){fprintf(stderr,"nonfinite state: tick=%d car=%d\n",tick,i);fatal=1;return 0;}
    d->flags=(!c->grounded?1:0)|(c->destroyed?2:0)|(d->start>=0?8:0);
    if(c->recoveries>rec){event(i,"recovery",c->recoveries-rec);suspicions++;}
    if(c->foliageBounces>fb){bounces+=c->foliageBounces-fb;event(i,"foliage",0);}
  }
  // Sweep-and-prune on X; handles arbitrary car dimensions, deterministic pair order.
  int order[FLEET];float radius=0;
  for(int i=0;i<fleetN;i++){order[i]=i;radius=fmaxf(radius,hypotf(fleet[i].c.p.halfL,fleet[i].c.p.halfW)+fabsf(fleet[i].c.p.bodyOfs));}
  qsort(order,fleetN,sizeof *order,byX);
  for(int a=0;a<fleetN;a++)for(int b=a+1;b<fleetN;b++){
    Car *c=&fleet[order[a]].c,*d=&fleet[order[b]].c;
    if(d->x-c->x>radius*2)break;
    if(fabsf(d->z-c->z)>radius*2)continue;
    if(carHitCar(c,d,&W))hits++;
  }
  for(int i=0;i<fleetN;i++){
    Driver *d=&fleet[i];Car *c=&d->c;
    contactCar=i;propsHitCar(&objects,&W,c,&d->previous);
    int sh=stateObjects.hits;spHitCar(&stateObjects,&W,c,0);stateHits+=(unsigned)(stateObjects.hits-sh);
    carBox(c,&d->previous);
    if(!sane(c)){fatal=1;fprintf(stderr,"nonfinite peer collision\n");return 0;}
    // Persistent overlap is suspicious; one solver correction is not a failed route.
    CarBox box;carBox(c,&box);colProbeCar(&W,&box);
    if(inject && !strcmp(inject,"penetration") && i==0 && tick>=30)box.maxDepth=1;
    d->penTicks=box.maxDepth>.15f?d->penTicks+1:0;
    if(d->penTicks>=12)d->flags|=4;
    if(d->penTicks==12){suspicions++;event(i,"penetration",(int)(box.maxDepth*1000));}
    if(!c->grounded){
      if(d->prevGround){d->launchY=c->y;d->maxY=c->y;d->air=0;}
      d->air++;d->maxY=fmaxf(d->maxY,c->y);
    }else if(!d->prevGround){
      if(d->air>=12){jumps++;landings++;if(fabsf(c->y-d->launchY)>1.5f){transitions++;event(i,"height-transition",(int)((c->y-d->launchY)*100));}}
      d->air=0;
    }
    // A deliberate flight has no support underneath; it is not automatically a hole.
    if(d->air==300){suspicions++;event(i,"long-flight",300);}
    d->wallTicks=fabsf(c->v)<.3f?d->wallTicks+1:0;
    if(d->wallTicks==600){suspicions++;event(i,"blocked-review",c->contacts);}
    d->prevGround=c->grounded;d->prevY=c->y;coverage(c->x,c->y,c->z);
  }
  return 1;
}
static void commands(void){
  static char line[128];static int len;char ch;
  while(read(STDIN_FILENO,&ch,1)==1){
    if(ch=='\n'){
      line[len]=0;int v;
      if(sscanf(line,"speed %d",&v)==1 && (v==1||v==4||v==20))speed=v;
      else if(sscanf(line,"pause %d",&v)==1)paused=v!=0;
      else if(!strcmp(line,"stop"))stopping=1;
      len=0;frame();
    }else if(len<(int)sizeof line-1)line[len++]=ch;
  }
}
#ifndef SANDBOX_NO_MAIN   // bots_swarm.c подключает этот файл и ставит свой main
int main(int argc,char **argv){
  const char *level=0,*road=0,*inject=0;int ticks=0,emit=4;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--level")&&i+1<argc)level=argv[++i];
    else if(!strcmp(argv[i],"--roads")&&i+1<argc)road=argv[++i];
    else if(!strcmp(argv[i],"--cars")&&i+1<argc)fleetN=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--seed")&&i+1<argc)campaignSeed=(uint32_t)strtoul(argv[++i],0,10);
    else if(!strcmp(argv[i],"--ticks")&&i+1<argc)ticks=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--emit")&&i+1<argc)emit=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--inject")&&i+1<argc)inject=argv[++i];
    else {fprintf(stderr,"unknown/incomplete argument: %s\n",argv[i]);return 2;}
  }
  if(!level||fleetN<1||fleetN>FLEET||ticks<0||emit<1||emit>600){fprintf(stderr,"level required, cars 1..%d, ticks >=0, emit 1..600\n",FLEET);return 2;}
  loadLevel(level);loadObjects();if(road)loadRoads(road);makeStarts();
  for(int i=0;i<fleetN;i++)spawn(i,0);
  began=now();fcntl(STDIN_FILENO,F_SETFL,O_NONBLOCK);frame();
  while(!stopping && (!ticks||tick<ticks)){
    if(!ticks)commands();
    if(paused){struct timespec nap={0,20000000};nanosleep(&nap,0);continue;}
    double start=now();int steps=ticks?emit:4*speed;
    for(int k=0;k<steps && (!ticks||tick<ticks);k++)if(!simulate(inject)){stopping=1;break;}
    if(!fatal)frame();
    if(!ticks){double wait=4./60-(now()-start);if(wait>0){struct timespec nap={0,(long)(wait*1e9)};nanosleep(&nap,0);}}
  }
  fprintf(stderr,"ticks=%d updates=%lu pairs=%lu voxels=%u observations=%lu wall=%.3fs\n",tick,updates,hits,covered,suspicions,now()-began);
  propsFree(&objects);spFree(&stateObjects);free(glassVisited);colFree(&W);free(file);free(roads);free(nxtStart);free(nxtList);
  return fatal?1:0;
}
#endif
