// Боты по маршрутам трамплинов (пункт 10 docs/handoff/LOOP_TERMINAL.md): тот же кадр, что viewer/main.c
// (carUpdate -> propsUpdate -> spUpdate, стекло ломается через spBreak, как onPropKick), без AI.
// Вход — build/sandbox/routes-l1.tsv (tools/cartest/routes.py): имя, старт xyz, направление dx dz, кромка xyz, стекло.
// На трамплин: скорости 40..120 км/ч шагом 10, подход прямо на кромку под углом −5/−2.5/0/2.5/5° к оси трамплина,
// промах у кромки вбок −1/0/1 м (135 заездов), старт на длине разгона маршрута, уже на скорости, газ держит скорость до
// кромки, после посадки — газ, руль прямо. Строка на заезд в stdout (TSV):
//   ramp kmh dh dl lip vlip landed lx ly lz surface flightS moved10 recovered flipped glass success
// surface: roof (под опорой на 3 м ниже есть ещё опора) / ground / bush / none. success — прошёл кромку, сел на колёса,
// за 10 с после посадки уехал на 15 м и дальше, без возврата на надёжное место и не на боку.
//   cc -std=c11 -O2 -DSKIN_HOST -I viewer tools/cartest/routes_run.c viewer/car.c viewer/col.c viewer/props.c \
//      viewer/stateprops.c viewer/coins.c -lm -o build/routes_run
//   build/routes_run level.shr routes.tsv [часть K из N]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"

static Props props; static StateProps sp; static ColWorld world; static Car car;
static int onKick(void *u, unsigned i, float dx, float dz) {
  (void)u; (void)dx; (void)dz;
  int b = spBreakOf(&sp, props.def[i].type); if (b < 0) return 0;
  float pos[3] = {props.def[i].x, props.def[i].y, props.def[i].z};
  return spBreak(&sp, (unsigned)b, pos, props.def[i].q);
}
static const char *surface(float x, float y, float z) {
  float g, n3[3], g2; int mat = 0;
  if (!colGroundMat(&world, x, z, y + 1.0f, y - 2.0f, &g, n3, &mat)) return "none";
  if (colGround(&world, x, z, g - 3.0f, -1e6f, &g2, 0)) return "roof";
  return mat == COL_MAT_FOLIAGE ? "bush" : "ground";
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: routes_run level.shr routes.tsv [K N]\n"); return 2; }
  int part = argc > 4 ? atoi(argv[3]) : 0, parts = argc > 4 ? atoi(argv[4]) : 1;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15);
  if (!data || fread(data, 1, size, f) != (size_t)size) return 2;
  fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40))) return 2;
  props.onKick = onKick;
  PropState *st0 = malloc(sizeof(PropState) * props.ninst); memcpy(st0, props.st, sizeof(PropState) * props.ninst);
  FILE *rt = fopen(argv[2], "r"); if (!rt) return 2;
  char name[64]; float sx, sy, sz, dx, dz, lx, ly, lz; int glass, idx = 0;
  const float dt = 1 / 60.f;
  while (fscanf(rt, "%63s %f %f %f %f %f %f %f %f %d", name, &sx, &sy, &sz, &dx, &dz, &lx, &ly, &lz, &glass) == 10) {
    if (idx++ % parts != part) continue;
    for (int kmh = 40; kmh <= 120; kmh += 10) for (int hi = -2; hi <= 2; hi++) for (int li = -1; li <= 1; li++) {
      // подход прямо на кромку под углом dh к оси трамплина, точка прицела сдвинута вбок на dl (вбок: (dz, -dx));
      // старт на той же длине разгона, что у маршрута, по линии подхода
      float dh = hi * 2.5f, dl = (float)li, a = dh * 0.0174533f, run = hypotf(lx - sx, lz - sz);
      float ux = dx * cosf(a) + dz * sinf(a), uz = -dx * sinf(a) + dz * cosf(a), h = atan2f(ux, uz);
      float ax = lx + dz * dl, az = lz - dx * dl, x0 = ax - ux * run, z0 = az - uz * run, gy;
      if (!colGround(&world, x0, z0, sy + 2.f, sy - 3.f, &gy, 0)) {
        printf("%s\t%d\t%.1f\t%.0f\t0\t0\t0\t0\t0\t0\tnostart\t0\t0\t0\t0\t%d\t0\n", name, kmh, dh, dl, glass >= 0 ? 0 : -1); continue;
      }
      memcpy(props.st, st0, sizeof(PropState) * props.ninst); props.havePreviousCar = 0;
      spFree(&sp); if (spInit(&sp, props.spr, props.sprSize)) return 2;
      carInit(&car, NULL, &world, x0, gy, z0, h);
      for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&car, &world, &in, dt); }
      carSetSpeed(&car, kmh / 3.6f);
      int rec0 = car.recoveries, passed = 0, air = 0, landed = 0, flipped = 0, miss = 0, nojump = 0;
      float vlip = 0, tl = 0, tp = 0, lxp = 0, lyp = 0, lzp = 0, airT = 0, flight = 0;
      const char *surf = "none"; float moved = 0;
      for (int fr = 0; fr < 25 * 60; fr++) {
        CarInput in = {0}; in.throttle = (!passed && car.v * 3.6f >= kmh) ? 0.f : 1.f;
        carUpdate(&car, &world, &in, dt); propsUpdate(&props, &world, &car, dt); spUpdate(&sp, &world, &car, NULL, dt);
        float t = fr * dt;
        if (!passed && (car.x - lx) * dx + (car.z - lz) * dz > 0.f) {                // плоскость кромки пройдена:
          float lat = fabsf((car.x - lx) * dz - (car.z - lz) * dx);                  // на самой кромке, а не мимо неё (3 м)
          if (lat <= 3.f && car.y >= ly - 1.5f) { passed = 1; vlip = car.v * 3.6f; tp = t; } else { miss = 1; break; }
        }
        if (passed && !air && t - tp > 1.5f) { nojump = 1; break; }                    // съехал с кромки без полёта
        if (passed && !landed) {
          if (!car.grounded) { airT += dt; if (airT >= 0.25f) air = 1; }
          else if (air) { landed = 1; tl = t; lxp = car.x; lyp = car.y; lzp = car.z; flight = airT; surf = surface(car.x, car.y, car.z); }
          else airT = 0;
          if (!air && passed && t > 20.f) break;
        }
        if (landed) { moved = hypotf(car.x - lxp, car.z - lzp); if (t - tl >= 10.f) break; }
        if (!passed && t > 15.f) break;
      }
      float U = 1.f - 2.f * (car.q[1] * car.q[1] + car.q[3] * car.q[3]);   // ось вверх тела, y-компонента
      flipped = U < 0.3f;
      int rec = car.recoveries != rec0, gb = glass >= 0 && (unsigned)glass < props.ninst ? props.st[glass].hidden : -1;
      int ok = passed && landed && !rec && !flipped && moved >= 15.f;
      if (miss) surf = "miss"; else if (nojump) surf = "nojump"; else if (!passed) surf = "blocked";
      printf("%s\t%d\t%.1f\t%.0f\t%d\t%.0f\t%d\t%.1f\t%.1f\t%.1f\t%s\t%.2f\t%.1f\t%d\t%d\t%d\t%d\n", name, kmh, dh, dl, passed, vlip, landed,
             lxp, lyp, lzp, surf, flight, moved, rec, flipped, gb, ok);
      fflush(stdout);
    }
  }
  return 0;
}
