/* CPU obstacle census, derived from props_sweep.c. Actual runtime update order.
   Every eligible PRP/SPR instance: eight headings at 50 km/h plus one drop,
   five seconds per trial. Suspects are repeated with only the target removed.
   SANDBOX_BREAK_OLD disables the real PRP break callback for negative control. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"

static Props props; static StateProps sp; static ColWorld world; static Car car;
static PropState *st0; static int kicked;
static int targetP=-1,targetS=-1,touchedEver,changedEver,brokenEver; static float lossMax;
static int onKick(void *u, unsigned i, float dx, float dz) {
  (void)u; (void)dx; (void)dz; kicked = 1; if((int)i==targetP)touchedEver=1;
  if(getenv("SANDBOX_BREAK_OLD"))return 0;
  int b = spBreakOf(&sp, props.def[i].type); if (b < 0) return 0;
  float pos[3] = {props.def[i].x, props.def[i].y, props.def[i].z};
  return spBreak(&sp, (unsigned)b, pos, props.def[i].q);
}
static int never(void *u, float x, float y, float z, float r) { (void)u; (void)x; (void)y; (void)z; (void)r; return 0; }
static void reset(void) {
  memcpy(props.st, st0, sizeof(PropState) * props.ninst); props.havePreviousCar = 0;
  spFree(&sp); if (spInit(&sp, props.spr, props.sprSize)) exit(2);
}
// заезд к точке (tx, ty, tz) с курса a на kmh (kmh < 0 — падение сверху с 5 м); -> застряла ли машина;
// *reach — ближе всего центр кузова подходил к точке (м)
static float reachM, propVmax, carVmax, propHmax, propYmin, plantK = 1.f; static int watchI = -1, plantDone;
static float reachYlo = -1e9f, reachYhi = 1e9f;   // «дошла» — только если кузов по высоте перекрывает предмет (PRP1)   // наблюдение: пик скорости предмета и машины за заезд
static int trial(float tx, float ty, float tz, float a, float kmh, float secs) {
  float sx, sz, gy, h;
  reachM = 1e9f; propVmax = carVmax = propHmax = 0.f; propYmin = 1e9f; plantDone = 0;   // до любого выхода: без старта заезда нет
  if (kmh < 0) {
    sx = tx; sz = tz; h = 0.3f;
    if (!colGround(&world, sx, sz, ty + 1.5f, ty - 6.f, &gy, 0)) gy = ty;
    carInit(&car, NULL, &world, sx, gy, sz, h); car.y = ty + 5.f; car.ry = car.y;
  } else {
    sx = tx - sinf(a) * 12.f; sz = tz - cosf(a) * 12.f; h = a;
    if (!colGround(&world, sx, sz, ty + 3.f, ty - 6.f, &gy, 0)) return -1;
    carInit(&car, NULL, &world, sx, gy, sz, h);
    for (int k = 0; k < 5; k++) { CarInput in = {0}; carUpdate(&car, &world, &in, 1 / 60.f); }
    carSetSpeed(&car, kmh / 3.6f);
  }
  float x0 = car.x, z0 = car.z;
  for (int fr = 0; fr < secs * 60; fr++) {
    CarInput in = {0}; in.throttle = kmh > 0 && car.v * 3.6f < kmh ? 1.f : 0.f;
    carUpdate(&car, &world, &in, 1 / 60.f);
    float before=hypotf(car.vel[0],car.vel[2]);
    propsUpdate(&props,&world,&car,1/60.f);spUpdate(&sp,&world,&car,NULL,1/60.f);
    int touching=0;
    if(targetP>=0){const PropState*q=&props.st[targetP];touching=q->hitCool>0;brokenEver|=q->hidden;changedEver|=q->hidden||hypotf(q->x-st0[targetP].x,q->z-st0[targetP].z)>.5f;}
    if(targetS>=0){const SpRun*q=&sp.run[targetS];touching=q->cool>0;changedEver|=q->state!=0||!q->alive||!q->colOn;}
    touchedEver|=touching;
    if(touching)lossMax=fmaxf(lossMax,before-hypotf(car.vel[0],car.vel[2]));
    CarBox b; carBox(&car, &b); float d = hypotf(b.x - tx, b.z - tz); if (b.y + b.hi < reachYlo || b.y + b.lo > reachYhi) d = 1e9f; if (d < reachM) reachM = d;
    float cv = sqrtf(car.vel[0] * car.vel[0] + car.vel[1] * car.vel[1] + car.vel[2] * car.vel[2]); if (cv > carVmax) carVmax = cv;
    if (watchI >= 0 && plantK != 1.f && !plantDone && !props.st[watchI].asleep) { float *pv = props.st[watchI].vel; pv[0] *= plantK; pv[2] *= plantK; plantDone = 1; }
    if (watchI >= 0 && !props.st[watchI].hidden) { const float *pv = props.st[watchI].vel; float v = sqrtf(pv[0] * pv[0] + pv[1] * pv[1] + pv[2] * pv[2]); if (v > propVmax) propVmax = v;
      float hv = sqrtf(pv[0] * pv[0] + pv[2] * pv[2]); if (hv > propHmax) propHmax = hv; if (props.st[watchI].y < propYmin) propYmin = props.st[watchI].y; }
  }
  return kmh > 0 && hypotf(car.x - x0, car.z - z0) < 6.f;   // не проехала и 6 м из 36 — упёрлась
}


/* Same real-world trial as props_sweep; enumerate all levels, retain no-contact
   separately, compare a suspect stop with precisely this object removed. */
static int reacts(unsigned i){const SpType*t=&sp.type[sp.inst[i].type];const SpState*s=&sp.state[t->firstState];for(unsigned j=0;j<s->nEvent;j++){int e=sp.event[s->firstEvent+j].event;if(e==7||e==8||e==11)return 1;}return 0;}
int main(int argc,char**argv){
 if(argc<2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);unsigned char*data=malloc(size);if(fread(data,1,size,f)!=(size_t)size)return 2;fclose(f);
 unsigned co=*(unsigned*)(data+92),po=*(unsigned*)(data+96),pv=*(unsigned*)(data+88),ce=size;if(po>co&&po<ce)ce=po;if(pv>co&&pv<ce)ce=pv;
 if(colInit(&world,data+co,ce-co)||propsInit(&props,data+po,*(unsigned*)(data+po+40))||spInit(&sp,props.spr,props.sprSize))return 2;
 props.onKick=onKick;st0=malloc(sizeof(PropState)*props.ninst);memcpy(st0,props.st,sizeof(PropState)*props.ninst);
 unsigned count[2]={props.ninst,sp.ninst};
 for(int kind=0;kind<2;kind++)for(unsigned i=0;i<count[kind];i++){
  if(argc>3&&(kind!=(argv[2][0]=='S')||i!=(unsigned)atoi(argv[3])))continue;
  if(kind&&(sp.type[sp.inst[i].type].kind||!reacts(i)||sp.inst[i].tag))continue;
  unsigned typ=kind?sp.inst[i].type:props.def[i].type;int brk=kind?-1:spBreakOf(&sp,typ);int expected=kind?1:(brk>=0&&sp.type[brk].nPiece>0);
  float x=kind?sp.inst[i].x:props.def[i].x,y=kind?sp.inst[i].y:props.def[i].y,z=kind?sp.inst[i].z:props.def[i].z;
  for(int d=0;d<9;d++){
   reset();touchedEver=changedEver=brokenEver=0;lossMax=0;targetP=kind?-1:i;targetS=kind?i:-1;watchI=targetP;float h=d*.78539816f,speed=d==8?-1:50;
   if(!kind){reachYlo=props.st[i].y-props.st[i].hy-.3f;reachYhi=props.st[i].y+props.st[i].hy+.3f;}
   else{reachYlo=-1e9f;reachYhi=1e9f;}
   int stuck=trial(x,y,z,h,speed,5);float endx=car.x,endz=car.z;int hit=touchedEver,changed=changedEver;float loss=lossMax,reach=reachM;int bad=hit&&((expected&&!kind?!brokenEver:!changed)||loss>3.f);float delta=0;
   if(bad){reset();targetP=targetS=watchI=-1;if(kind){sp.run[i].alive=0;sp.run[i].colOn=0;}else props.st[i].hidden=1;
    trial(x,y,z,h,speed,5);delta=hypotf(car.x-endx,car.z-endz);
    if(changed&&(!expected||kind||brokenEver)&&delta<2.f)bad=0;
   }
   const char*status=stuck<0?"no_ground":!hit?"no_contact":bad?"candidate":"pass";
   printf("{\"family\":\"breakable\",\"status\":\"%s\",\"kind\":\"%c\",\"id\":%u,\"type\":%u,\"x\":%.4f,\"y\":%.4f,\"z\":%.4f,\"heading\":%.8f,\"speed\":%.1f,\"expected_break\":%d,\"touched\":%d,\"changed\":%d,\"loss\":%.3f,\"without_delta\":%.3f,\"reach\":%.3f}\n",status,kind?'S':'P',i,typ,x,y,z,h,speed,expected,hit,changed,loss,delta,reach);
  }
 }
 return 0;
}
