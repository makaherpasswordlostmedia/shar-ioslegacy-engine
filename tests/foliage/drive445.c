// Проезд одной машины через место уровня тем же кадром, что viewer/main.c: carUpdate -> propsUpdate -> spUpdate
// (предметы PRP1 ломаются через spBreak, как onPropKick). На каждом кадре видно, кто отнял скорость:
// мир COL1 (тип контакта), предмет PRP1 (номер, тип), стейтпроп SPR1 (номер, тип, класс, объём).
//   cc -std=c11 -O2 -DSKIN_HOST -I viewer tools/cartest/drive.c viewer/car.c viewer/col.c viewer/props.c viewer/coins.c -lm -o build/drive
//   build/drive level.shr x z heading kmh seconds [y] [steer] [verbose]
//   y: высота старта (ищем опору от y+3 вниз; по умолчанию самая верхняя опору в точке)
// Итог строкой SUMMARY: сколько проехал по курсу, где остановился, кто упёрся, какие стёкла разбиты.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "../../viewer/stateprops.c"   // статические hitVolume/centerW: объяснить, какой объём упёрся
#include "props.h"

static Props props; static StateProps sprops; static ColWorld world; static Car car;
static int onKick(void *u, unsigned i, float dx, float dz) {       // как main.c onPropKick, без частиц и звука
  (void)u; (void)dx; (void)dz;
  int b = spBreakOf(&sprops, props.def[i].type); if (b < 0) return 0;
  float pos[3] = {props.def[i].x, props.def[i].y, props.def[i].z};
  return spBreak(&sprops, (unsigned)b, pos, props.def[i].q);
}
static float hs(const Car *c) { return sqrtf(c->vel[0] * c->vel[0] + c->vel[2] * c->vel[2]) * 3.6f; }

int main(int argc, char **argv) {
  if (argc < 7) { fprintf(stderr, "usage: drive level.shr x z heading kmh seconds [y] [steer] [verbose]\n"); return 2; }
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15);
  if (!data || fread(data, 1, size, f) != (size_t)size) return 2;
  fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40)) ||
      spInit(&sprops, props.spr, props.sprSize)) { fprintf(stderr, "level load failed\n"); return 2; }
  props.onKick = onKick;
  float x = atof(argv[2]), z = atof(argv[3]), h = atof(argv[4]), kmh = atof(argv[5]), secs = atof(argv[6]);
  float y0 = argc > 7 ? atof(argv[7]) : 1e6f, steer = argc > 8 ? atof(argv[8]) : 0.f; int verbose = argc > 9 ? atoi(argv[9]) : 1;
  float g = 0; colGround(&world, x, z, y0 < 1e5f ? y0 + 3.f : 300.f, -1e6f, &g, 0);
  carInit(&car, NULL, &world, x, g, z, h);
  for (int i = 0; i < 30; i++) { CarInput in = {0}; carUpdate(&car, &world, &in, 1 / 60.f); propsUpdate(&props, &world, &car, 1 / 60.f); spUpdate(&sprops, &world, &car, NULL, 1 / 60.f); }
  carSetSpeed(&car, getenv("FOLIAGE_START_REST") ? 0.f : kmh / 3.6f);
  const float dt = 1 / 60.f, fx = sinf(h), fz = cosf(h), sx = car.x, sz = car.z;
  float maxAlong = 0, maxY = car.y, lossWorld = 0, lossProp = 0, lossSp = 0; int stuck = 0, lastSp = -1, lastSpVol = -1, nrev = 0, revWhyAll = 0, nrec = 0;
  unsigned char hid0[1024] = {0}; for (unsigned i = 0; i < props.ninst && i < 1024; i++) hid0[i] = (unsigned char)props.st[i].hidden;
  printf("START %.1f %.1f %.1f heading %.3f, %.0f km/h\n", car.x, car.y, car.z, h, kmh);
  for (int fr = 0; fr < secs * 60; fr++) {
    CarInput in = {0}; in.throttle = car.v * 3.6f < kmh ? 1.f : 0.f; in.steer = steer;
    float v0 = hs(&car); int rev0 = car.reverts, rec0 = car.recoveries;
#ifdef COL_DEBUG
    { extern int colDebug; const char *e = getenv("DBGF"); colDebug = e && fr >= atoi(e) && fr <= atoi(e) + 1; if (colDebug) printf("=== frame %d\n", fr); }
#endif
    carUpdate(&car, &world, &in, dt);
    float v1 = hs(&car);
    propsUpdate(&props, &world, &car, dt);
    float v2 = hs(&car);
    // стейтпроп, в который упрётся кузов в spUpdate (тот же hitVolume)
    CarBox cb; carBox(&car, &cb); int who = -1, wvol = -1; float wd = 0;
    for (unsigned i = 0; i < sprops.ninst; i++) {
      SpRun *r = &sprops.run[i]; const SpType *T = TY(&sprops, i);
      if (!r->alive || !r->colOn || !T->nCol) continue;
      for (unsigned k = 0; k < T->nCol; k++) {
        const SpCol *C = &sprops.col[T->firstCol + k]; if (C->second && !r->col2On) continue;
        float nx, nz, d, impact; if (hitVolume(r, C, &cb, car.vel, &nx, &nz, &d, &impact) && d > wd) { wd = d; who = (int)i; wvol = (int)k; }
      }
    }
    spUpdate(&sprops, &world, &car, NULL, dt);
    float v3 = hs(&car);
    float along = (car.x - sx) * fx + (car.z - sz) * fz; if (along > maxAlong) maxAlong = along; if (car.y > maxY) maxY = car.y;
    if (v1 < v0 - .5f) lossWorld += v0 - v1; if (v2 < v1 - .5f) lossProp += v1 - v2; if (v3 < v2 - .5f) lossSp += v2 - v3;
    if (who >= 0) { lastSp = who; lastSpVol = wvol; }
    int ev = car.contacts > 0 || v2 < v1 - .5f || v3 < v2 - .5f || who >= 0 || car.reverts != rev0 || car.recoveries != rec0;
    if (car.reverts != rev0) { nrev++; revWhyAll |= car.revWhy; } if (car.recoveries != rec0) nrec++;
    if (verbose > 1 || (verbose && ev))
      printf("t=%.2f pos %.1f %.1f %.1f v %.0f->%.0f->%.0f->%.0f gr %d wh %d | wall %d%s%s", fr * dt, car.x, car.y, car.z, v0, v1, v2, v3,
             car.grounded, car.wheels, car.contacts, car.contacts ? " type" : "", "");
    if (verbose > 1 || (verbose && ev)) {
      for (int k = 0; k < car.contacts; k++) printf(" %d(n %.2f %.2f)", car.ctype[k], car.cnx[k], car.cnz[k]);
      if (car.reverts != rev0) printf(" | REVERT x%d why %d", car.reverts - rev0, car.revWhy);
      if (car.recoveries != rec0) printf(" | RECOVERY");
      if (who >= 0) { const SpType *T = TY(&sprops, (unsigned)who); SpRun *r = &sprops.run[who];
        printf(" | SP #%d type %u cls %u mass %.0f state %u vol %d depth %.2f at %.1f %.1f %.1f", who, sprops.inst[who].type, T->cls, T->mass,
               r->state, wvol, wd, r->x, r->y, r->z); }
      for (unsigned i = 0; i < props.ninst && i < 1024; i++) if (props.st[i].hidden != hid0[i]) { printf(" | PRP #%u type %u hidden", i, props.def[i].type); hid0[i] = 1; }
      printf("\n");
    }
    if (hs(&car) < 3.f && fr > 30) { if (++stuck > 180) break; } else stuck = 0;
  }
  printf("SUMMARY %.0f km/h: along %.1f m (max %.1f), end %.1f %.1f %.1f v %.0f km/h, maxY %.1f, lost km/h world %.0f props %.0f stateprops %.0f%s",
         kmh, (car.x - sx) * fx + (car.z - sz) * fz, maxAlong, car.x, car.y, car.z, hs(&car), maxY, lossWorld, lossProp, lossSp, stuck > 180 ? ", STOPPED" : "");
  if (nrev) printf(", reverts %d (why mask %d)", nrev, revWhyAll);
  if (nrec) printf(", recoveries %d", nrec);
  if (lastSp >= 0) printf(", last SP #%d type %u cls %u vol %d", lastSp, sprops.inst[lastSp].type, TY(&sprops, (unsigned)lastSp)->cls, lastSpVol);
  printf("\n");
  return 0;
}
