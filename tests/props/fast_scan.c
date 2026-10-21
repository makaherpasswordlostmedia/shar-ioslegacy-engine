// Native (Mac) harness for viewer/homer.c: movement numbers, COL1 collision and the Ф3 episode without the PSP.
//   tests/homer/host.sh            (builds with -DSKIN_HOST and runs on build/level.shr + build/homer.shr)
// Same modules as the engine: homer.c, skin.c (host mode), col.c, car.c, props.c, stateprops.c, coins.c.
// Prints one line per check with the measured number and the expected (original) value; exit code = failed checks.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "homer.h"
#include "props.h"
#include "stateprops.h"
#include "coins.h"

static ColWorld world; static Car car; static Props props; static StateProps sp; static Coins coins;
static int haveSP, haveCoins, fails;
static float doorOpen, doorMax; static int doneIn = -1, doneOut = -1;
static void onDoor(void *u, float o) { (void)u; doorOpen = o; if (o > doorMax) doorMax = o; }
static void onDone(void *u, int in) { (void)u; if (in) doneIn = 1; else doneOut = 1; }

static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(16, (sz + 15) & ~15u);
  fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; }
  return m;
}
static void check(const char *what, float got, float lo, float hi, const char *expect) {
  int ok = got >= lo && got <= hi; if (!ok) fails++;
  printf("%-4s %-46s %8.3f   (%s)\n", ok ? "ok" : "FAIL", what, got, expect);
}


// Равенство кеша твёрдости Гомера (HOMER_SOLID_CACHE_OLD): Гомер идёт на реальные стейтпропы и пропы уровня с разных сторон при разных dt —
// хеш всех поз и число выталкиваний должны совпасть в сборках с кешем и без (-DHOMER_SOLID_CACHE_OLD=1).
//   cc ... -DSKIN_HOST [-DHOMER_SOLID_CACHE_OLD=1] tests/homer/solid_cache.c viewer/{homer,skin,col,car,props,stateprops,coins}.c -lm
static unsigned long long hsh = 1469598103934665603ULL;
static void hashf(float v) { unsigned u; memcpy(&u, &v, 4); hsh = (hsh ^ u) * 1099511628211ULL; }
// Сверка «быстрого расчёта» стейтпропов и пропов (SP_SCAN_OLD, PROP_HITSLOW_OLD): машина едет с разным вводом через реальные предметы L1,
// каждый кадр spUpdate + propsUpdate; хеш положения машины, состояний и поз предметов одинаков в сборках с флагами и без.
//   cc ... -DSKIN_HOST [-DSP_SCAN_OLD=1 -DPROP_HITSLOW_OLD=1] tests/props/fast_scan.c viewer/{col,car,props,stateprops,coins}.c -lm
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) return 1;
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) return 1;
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f);
  unsigned end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff);
  if (!cm || colInit(&world, cm, end - colOff)) return 1;
  if (propOff) { unsigned char *ph = readAt(f, propOff, 64); unsigned sz = !memcmp(ph, "PRP2", 4) ? *(unsigned *)(ph + 40) : 0;
    if (sz) { unsigned char *pm = readAt(f, propOff, sz);
      if (pm && propsInit(&props, pm, sz) == 0) { if (props.spr && spInit(&sp, props.spr, props.sprSize) == 0) haveSP = 1; } } }
  fclose(f);
  unsigned hitsSp = 0, movedProps = 0;
  unsigned ninst = (haveSP ? sp.ninst : 0) + props.ninst, runs = 0, frames = 0;
  for (unsigned k = 0; k < ninst; k += (ninst > 150 ? ninst / 150 : 1)) {
    float tx, tz, ty;
    if (haveSP && k < sp.ninst) { tx = sp.run[k].x; ty = sp.run[k].y; tz = sp.run[k].z; } else { unsigned j = k - (haveSP ? sp.ninst : 0); if (j >= props.ninst) break; tx = props.st[j].x; ty = props.st[j].y; tz = props.st[j].z; }
    for (int side = 0; side < 3; side++) {
      float ang = side * 2.1f + (k % 5) * .4f, sx = tx - sinf(ang) * 25.f, sz = tz - cosf(ang) * 25.f;
      carInit(&car, NULL, &world, sx, ty + 1.f, sz, ang);
      for (int i = 0; i < 400; i++) {
        CarInput ci = {0}; ci.throttle = (side == 2 && i < 60) ? 0.f : 1.f; ci.steer = (side == 1) ? .05f * sinf(i * .05f) : 0.f; ci.brake = (i > 330) ? 1.f : 0.f;
        float dt = 1.f / 30.f;
        carUpdate(&car, &world, &ci, dt);
        if (haveSP) spUpdate(&sp, &world, &car, NULL, dt);
        propsUpdate(&props, &world, &car, dt);
        hashf(car.x); hashf(car.y); hashf(car.z); hashf(car.vel[0]); hashf(car.vel[2]);
        frames++; }
      runs++;
      if (haveSP) for (unsigned i = 0; i < sp.ninst; i++) hitsSp += sp.run[i].state != 0;
      for (unsigned i = 0; i < props.ninst; i++) movedProps += props.st[i].hidden || !props.st[i].asleep;
      if (haveSP) for (unsigned i = 0; i < sp.ninst; i++) { hashf((float)sp.run[i].state); hashf(sp.run[i].t); hashf(sp.run[i].x); hashf(sp.run[i].y); hashf(sp.run[i].z); }
      for (unsigned i = 0; i < props.ninst; i++) { hashf(props.st[i].x); hashf(props.st[i].y); hashf(props.st[i].z); hashf((float)props.st[i].hidden); }
    }
  }
  printf("hit stateprops %u, props touched %u; ", hitsSp, movedProps); printf("runs %u frames %u sp %u props %u hash %016llx\n", runs, frames, haveSP ? sp.ninst : 0, props.ninst, hsh); return 0;
}
