// Actual COL1 + Homer movement: nearby ground/roof samples and finite hedge volumes.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "homer.h"
static ColWorld world;
static Homer h;
static int failures;
static void check(const char *name, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", name); failures += !ok; }
static void step(int jump) {
  HomerInput in = {0}; in.jump = jump;
  homerUpdate(&h, &world, NULL, &in, 1.f/60.f);
  HomerEvent e; while (homerPopEvent(&h, &e)) {}
}
int main(int argc, char **argv) {
  if (argc != 3) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f,0,SEEK_END); long size=ftell(f); rewind(f);
  unsigned char *data=aligned_alloc(16,(size+15)&~15);
  if (!data || fread(data,1,size,f)!=(size_t)size) return 2; fclose(f);
  unsigned co=*(unsigned*)(data+92),po=*(unsigned*)(data+96),pv=*(unsigned*)(data+88),ce=(unsigned)size;
  if(po>co&&po<ce)ce=po; if(pv>co&&pv<ce)ce=pv;
  if(colInit(&world,data+co,ce-co))return 2;
  SkinModel *model=skinLoad(argv[2]);if(!model||homerInit(&h,model))return 2;
  const float yards[][2]={{220,160},{220,185},{235,185},{245,185},{235,150},{210,160}};
  int grounds=0,jumps=0;
  for(unsigned i=0;i<sizeof yards/sizeof yards[0];i++) {
    float x=yards[i][0],z=yards[i][1],g;
    if(!colGround(&world,x,z,12,-10,&g,0)) {printf("no ground %.2f %.2f\n",x,z);continue;}
    grounds++;homerPlace(&h,&world,x,g,z,0);for(int n=0;n<10;n++)step(0);
    float base=h.y,peak=h.y;int landed=0;
    for(int n=0;n<100;n++){step(n==0);if(h.y>peak)peak=h.y;if(n>5&&h.grounded)landed=1;}
    int ok=peak-base>1.7f&&peak-base<2.05f&&landed;jumps+=ok;
    printf("yard %.2f %.2f base=%.3f height=%.3f landed=%d drift=%.3f\n",x,z,base,peak-base,landed,hypotf(h.x-x,h.z-z));
  }
  check("six neighbourhood samples have support",grounds==6);check("sample jumps take off and land",jumps==6);
  // Horizontal capsules include the original hedge units. At their centre top, standing must
  // not be pushed sideways by the same surface that supports the feet.
  int capsules=0,stable=0,jumpable=0, obstructed=0;
  for(unsigned i=0;i<world.ncyl;i++) {
    const ColCyl *c=&world.cyl[i];
    if(c->flat||c->r<.65f||c->r>.75f||c->halfLen<2.2f||c->halfLen>2.4f||fabsf(c->axis[1])>.1f)continue;
    float g;if(!colGround(&world,c->c[0],c->c[2],c->c[1]+2,-100,&g,0))continue;
    homerPlace(&h,&world,c->c[0],g,c->c[2],0);
    CarBox probe={0};probe.x=h.x;probe.z=h.z;probe.y=h.y;probe.fz=1;
    probe.hw=probe.hl=HOMER_RADIUS;probe.lo=HOMER_STEP;probe.hi=HOMER_HEIGHT;
    if(colProbeCar(&world,&probe)>0||fabsf(h.y-g)>.05f){obstructed++;continue;}
    capsules++;
    for(int n=0;n<60;n++)step(0);
    int ok=fabsf(h.y-g)<.05f&&hypotf(h.x-c->c[0],h.z-c->c[2])<.05f;
    stable+=ok;float base=h.y,peak=base;
    for(int n=0;n<100;n++){step(n==0);if(h.y>peak)peak=h.y;}
    jumpable+=peak-base>1.7f;
    if(!ok)printf("unstable hedge %u xz=%.3f,%.3f y=%.3f->%.3f drift=%.3f\n",i,c->c[0],c->c[2],g,h.y,hypotf(h.x-c->c[0],h.z-c->c[2]));
  }
  printf("hedges unobstructed=%d stable=%d jumpable=%d blocked_by_other_geometry=%d\n",capsules,stable,jumpable,obstructed);
  check("hedge fixtures exist",capsules>50);check("stand on hedge without lateral ejection",stable==capsules);
  check("jump from hedge",jumpable==capsules);
  colFree(&world);skinFree(model);free(data);
  return failures;
}
