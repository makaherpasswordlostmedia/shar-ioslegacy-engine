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
static unsigned long long hsh = 1469598103934665603ULL; static unsigned pushes, calls;
static void hashf(float v) { unsigned u; memcpy(&u, &v, 4); hsh = (hsh ^ u) * 1099511628211ULL; }
static int solidAll(void *u, float *x, float *z, float y, float r, float *top, float *nx, float *nz) {
  (void)u; int hit = 0; calls++;
  if (haveSP) hit |= homerSolidSprops(&sp, x, z, y, r, top, nx, nz);
  if (props.st) hit |= propsSolidHomer(&props, x, z, y, r, HOMER_STEP, HOMER_HEIGHT, top, nx, nz);
  pushes += hit; return hit;
}
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr", *hom = argc > 2 ? argv[2] : "build/homer.shr";
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
  SkinModel *m = skinLoad(hom); if (!m) return 1;
  static Homer H; if (homerInit(&H, m)) return 1;
  H.solid = solidAll; H.solidUser = 0;
  static const float dts[3] = {1.f / 60.f, 1.f / 30.f, 1.f / 20.f};
  unsigned ninst = (haveSP ? sp.ninst : 0) + props.ninst, walks = 0;
  for (unsigned k = 0; k < ninst; k += (ninst > 400 ? ninst / 400 : 1)) {
    float tx, ty, tz;
    if (haveSP && k < sp.ninst) { tx = sp.run[k].x; ty = sp.run[k].y; tz = sp.run[k].z; } else { unsigned j = k - (haveSP ? sp.ninst : 0); if (j >= props.ninst) break; tx = props.st[j].x; ty = props.st[j].y; tz = props.st[j].z; }
    for (int side = 0; side < 4; side++) {
      float ang = side * 1.5708f + (k % 7) * .3f, sx = tx - sinf(ang) * 3.f, sz = tz - cosf(ang) * 3.f;
      homerPlace(&H, &world, sx, ty + 1.f, sz, ang);
      float dt = dts[(k + side) % 3]; HomerInput in; memset(&in, 0, sizeof in); in.camYaw = ang; in.my = 1.f; in.dash = side & 1;
      for (int i = 0; i < 120; i++) { homerUpdate(&H, &world, NULL, &in, dt); hashf(H.x); hashf(H.y); hashf(H.z); hashf(H.vx); hashf(H.vz); }
      walks++; }
  }
  printf("walks %u calls %u pushes %u hash %016llx\n", walks, calls, pushes, hsh); return 0;
}
