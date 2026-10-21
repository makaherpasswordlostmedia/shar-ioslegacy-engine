#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"
extern int colDebug;
static ColWorld w;
int loadCol(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) return -1; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); fread(d, 1, n, f); fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96);
  unsigned end = n; if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff);
  return colInit(&w, cm, end - colOff);
}
// usage: ramp level.shr x z heading kmh seconds [verbose] [steer]
int main(int argc, char **argv) {
  if (loadCol(argv[1])) { puts("col fail"); return 1; }
  float x = atof(argv[2]), z = atof(argv[3]), h = atof(argv[4]), kmh = atof(argv[5]), secs = atof(argv[6]);
  int verbose = argc > 7 ? atoi(argv[7]) : 1; float steer = argc > 8 ? atof(argv[8]) : 0;
  static Car car; float g = 0; colGround(&w, x, z, 200, -1e6f, &g, 0);
  carInit(&car, NULL, &w, x, g, z, h);
  for (int i = 0; i < 30; i++) { CarInput in = {0}; carUpdate(&car, &w, &in, 1 / 60.f); }
  carSetSpeed(&car, kmh / 3.6f);
  float dt = 1 / 60.f; int rev0 = car.reverts, rec0 = car.recoveries, wallFrames = 0, revFrames = 0; float maxY = car.y, minV = 1e9, v0 = car.v;
  float maxHit = 0;
  for (int fr = 0; fr < secs * 60; fr++) {
    CarInput in = {0}; in.throttle = car.v * 3.6f < kmh ? 1 : 0; in.steer = steer;
    int r0 = car.reverts;
    { char *e = getenv("DBG"); if (e) { int a = atoi(e); colDebug = fr >= a && fr <= a + 2; if (colDebug) printf("=== frame %d\n", fr); } }
    carUpdate(&car, &w, &in, dt);
    if (car.y > maxY) maxY = car.y;
    int wall = car.contacts > 0; wallFrames += wall; revFrames += car.reverts != r0;
    if (car.hitSpeed > maxHit && wall) maxHit = car.hitSpeed;
    if (verbose && (wall || car.reverts != r0 || verbose > 1))
      printf("t=%.3f pos %.2f %.2f %.2f v %.1f km/h vy %.1f pitch %.1f wh %d gr %d | ct %d%s", fr * dt, car.x, car.y, car.z, car.v * 3.6f, car.vy,
             car.pitch * 57.3f, car.wheels, car.grounded, car.contacts, car.reverts != r0 ? " REVERT" : "");
    if (verbose && (wall || car.reverts != r0)) { printf(" why %d hit %.1f pen %.3f", car.revWhy, car.hitSpeed, car.pen);
      for (int k = 0; k < car.contacts; k++) printf(" [type %d n %.2f %.2f]", car.ctype[k], car.cnx[k], car.cnz[k]); }
    if (verbose && (wall || car.reverts != r0 || verbose > 1)) printf("\n");
  }
  printf("SUMMARY start %.1f km/h end pos %.1f %.1f %.1f v %.1f km/h maxY %.2f wallFrames %d revertFrames %d reverts %d recoveries %d maxWallHit %.1f dmg %.3f\n",
         kmh, car.x, car.y, car.z, car.v * 3.6f, maxY, wallFrames, revFrames, car.reverts - rev0, car.recoveries - rec0, maxHit, car.damage);
  return 0;
}
