// №432: actual ramp018/jumpzone9 flight in the same car/col/game code as PSP.
#include "world.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static int bad;
#define NEED(x, ...) do { printf("%s ", (x)?"ok":"FAIL"); printf(__VA_ARGS__); puts(""); if(!(x))bad++; } while(0)
static int yard(const ColWorld*w, const Car*c) {
  for(unsigned i=0;i<w->ndeath;i++) { const ColPad*d=w->death+i; if(strcmp(d->name,"R6D01"))continue;
    float ex=0,ez=0;const float*a[3]={d->ax,d->ay,d->az};
    for(int j=0;j<3;j++){ex+=fabsf(a[j][0])*d->h[j];ez+=fabsf(a[j][2])*d->h[j];}
    if(fabsf(c->x-d->c[0])<=ex && fabsf(c->z-d->c[2])<=ez)return 1;
  }return 0;
}
static void run(int kmh,int clear) {
  static BotWorld w;bwNew(&w);bwPlace(&w,247.f,7.f,-507.698f,1.5707963f);
  // Only horizontal entry velocity. Lift, pitch, vertical velocity, gravity,
  // ramp geometry, collisions and gameDeath all come from the real world.
  w.car.v=kmh/3.6f;w.car.vel[0]=w.car.v;
  int launch=-1,land=-1,death=-1,over=0,premature=0;float lx=0,ly=0,lz=0;
  for(int f=0;f<420;f++) {
    bwStep(&w,GP_R,0,0);Car*c=&w.car;
    if(bwLastDeathZone>=0){death=f;printf("DEATH entry%d frame%d %s -> %.3f %.3f %.3f grounded%d flight%d\n",kmh,f,bwCol()->death[bwLastDeathZone].name,c->x,c->y,c->z,c->grounded,c->flightZone);break;}
    if(launch<0&&!c->grounded&&c->flightZone>=0&&!strcmp(bwCol()->zone[c->flightZone].name,"jumpzone9")) {launch=f;printf("TAKEOFF entry%d frame%d %.3f %.3f %.3f v%.3f vy%.3f\n",kmh,f,c->x,c->y,c->z,c->v*3.6f,c->vy);}
    if(launch>=0&&!c->grounded&&yard(bwCol(),c)) {over++; if(gameDeathAt(&w.G)>=0)premature++;}
    if(launch>=0&&c->grounded&&land<0){land=f;lx=c->x;ly=c->y;lz=c->z;printf("LAND entry%d frame%d %.3f %.3f %.3f\n",kmh,f,lx,ly,lz);if(!clear)break;}
    if(land>=0&&f>land+60)break;
  }
  NEED(launch>=0,"entry%d actual ramp takeoff frame%d",kmh,launch);
  NEED(over>=20&&premature==0,"entry%d flight above yard %d frames, premature death %d",kmh,over,premature);
  if(clear) {
    NEED(land>launch&&death<0&&!yard(bwCol(),&w.car),"overflight: lands outside yard, alive 1s after landing; land%d death%d final %.3f %.3f %.3f",land,death,w.car.x,w.car.y,w.car.z);
    NEED(w.car.flightZone<0,"landing clears flight provenance (%d)",w.car.flightZone);
  } else {
    NEED(launch>=0&&death>launch,"undershoot returns after the flight: launch%d death%d",launch,death);
    const ColPad*d=death>=0?bwCol()->death+bwLastDeathZone:0;
    NEED(d&&hypotf(w.car.x-d->apex[0],w.car.z-d->apex[2])<.1f&&fabsf(w.car.v)<.01f,"undershoot authored return position and zero speed");
  }
}
int main(int n,char**v) {if(n<3||bwData(v[1],v[2],0))return 2;run(120,1);run(45,0);
  static BotWorld w;bwNew(&w);bwPlace(&w,247,7,-507.698f,1.5707963f);
  for(unsigned j=0;j<bwCol()->nzone;j++)if(!strcmp(bwCol()->zone[j].name,"jumpzone9"))w.car.flightZone=(int)j;carPlace(&w.car,bwCol(),274,20,-515,1.5707963f);
  NEED(w.car.flightZone<0&&gameDeathAt(&w.G)>=0,"placement ends exemption; ordinary R6 air still deadly");
  printf("ramp432: %s\n",bad?"FAIL":"PASS");return bad?1:0;}
