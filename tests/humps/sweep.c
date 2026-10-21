// Правка Роба 200 (03.10) — сверка всего семейства на всех уровнях: «кусты медленно выталкивают в разные стороны».
// Каждая лежачая капсула-горб уровня (|ось.y| <= 0.3, длина >= COL_HUMP_LEN): три места вдоль оси, обе стороны; со стороны, где
// верх капсулы над землёй не выше COL_HUMP (горб, переезжается), машина едет поперёк оси на 3 м/с 6 с. Меряется наибольший сдвиг
// кузова за кадр сверх скорости поперёк курса (толчок вбок) — до схода за капсулу. Итог: заездов, толчков > 0.1 м/кадр.
//   cc ... tests/humps/sweep.c viewer/car.c viewer/col.c -lm && ./sweep LEVEL.shr   (красный: -DCAPSULE_STADIUM=1 -DHUMP_SIDE_ONLY=1)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W;
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  int runs = 0, pushed = 0, crossed = 0, stuck = 0; float worst = 0.f; int verbose = getenv("SWEEP_V") != NULL;
  for (unsigned i = 0; i < W.ncyl; i++) {
    const ColCyl *C = &W.cyl[i]; float axl = hypotf(C->axis[0], C->axis[2]);
    if (C->halfLen <= 0.f || fabsf(C->axis[1]) > .3f || axl < 1e-4f || 2.f * C->halfLen * axl < COL_HUMP_LEN) continue;
    float ux = C->axis[0] / axl, uz = C->axis[2] / axl;
    for (int st = 1; st <= 3; st++) for (int side = -1; side <= 1; side += 2) {
      { const char *o = getenv("SWEEP_ONLY"); unsigned oc; int os, od; if (o && sscanf(o, "%u,%d,%d", &oc, &os, &od) == 3 && (oc != i || os != st || od != side)) continue; }
      float t = (st * .25f - .5f) * 2.f * C->halfLen, ax = C->c[0] + C->axis[0] * t, az = C->c[2] + C->axis[2] * t, top = C->c[1] + C->axis[1] * t + C->r;
      float px = -uz * side, pz = ux * side, sx = ax + px * (C->r + 5.f), sz = az + pz * (C->r + 5.f), g;
      if (!colGround(&W, sx, sz, top + 1.f, top - 6.f, &g, 0)) continue;
      if (top - g > COL_HUMP) continue;                         // сторона-стена: там капсула — не горб
      Car c; carInit(&c, NULL, &W, sx, g, sz, atan2f(-px, -pz));
      for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
      carSetSpeed(&c, 3.f); float mx = 0.f; int over = 0;
      for (int fr = 0; fr < 360; fr++) {
        CarInput in = {1, 0, 0}; if (c.v > 3.f) in.throttle = 0;
        float ox = c.x, oz = c.z, vx = c.vel[0], vz = c.vel[2]; int rec0 = c.recoveries, rev0 = c.reverts;
        carUpdate(&c, &W, &in, 1 / 60.f);
        if (c.recoveries != rec0 || c.reverts != rev0) { stuck++; break; }   // сел брюхом и подъём машины на место — не толчок, считается отдельно
        float dx = c.x - ox - vx / 60.f, dz = c.z - oz - vz / 60.f, fx = sinf(c.h), fz = cosf(c.h), lat = fabsf(-fz * dx + fx * dz);
        float across = (c.x - ax) * px + (c.z - az) * pz;            // > 0 — своя сторона, < -(r + 2.7) — за капсулой
        if (across < -(C->r + 3.f)) { over = 1; break; }
        if (lat > mx) mx = lat;
        if (getenv("SWEEP_TRACE") && (lat > .05f || fr % 20 == 0)) printf("    кадр %d pos %.2f %.2f %.2f v %.2f вбок %.2f ct %d wallV %.1f prim %d#%u поперёк %.2f\n", fr, c.x, c.y, c.z, c.v, lat,
                                                    c.contacts, c.wallV, c.wallV > 0 ? c.wallType : -1, c.wallV > 0 ? c.wallIdx : 0, across);
      }
      runs++; crossed += over; if (mx > .1f) pushed++; if (mx > worst) worst = mx;
      if (verbose && mx > .1f) printf("  cyl %u место %d сторона %+d: толчок вбок %.2f м/кадр, %s | c %.2f %.2f %.2f ось %.2f %.2f %.2f r %.2f half %.2f | старт %.2f %.2f верх над землёй %.2f конец %.2f %.2f\n",
                                       i, st, side, mx, over ? "переехал" : "не переехал", C->c[0], C->c[1], C->c[2], C->axis[0], C->axis[1], C->axis[2], C->r, C->halfLen,
                                       sx, sz, top - g, c.x, c.z);
    }
  }
  printf("RESULT %s: заездов через горбы %d, переехали %d, сели брюхом %d, с толчком вбок > 0,1 м/кадр %d (наибольший %.2f)\n", argv[1], runs, crossed, stuck, pushed, worst);
  return 0;
}
