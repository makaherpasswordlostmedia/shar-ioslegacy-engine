// №485: Obliteratatron (и любая машина) с места на полном газу: тангаж за 2,4 с. PS2 (ps2-oblit-launch.yaml): пик 5,5–6,1° в первые 8 кадров, дальше 2–4°, на ходу 1–3°; на задние колёса НЕ встаёт.
// Ровная площадка, тот же carUpdate, 50 Гц. cc -std=c11 -O2 -I viewer tests/cars/wheelie.c viewer/car.c viewer/col.c -lm -o wheelie && ./wheelie [машина] [предел°]   -> PASS/FAIL (пик не больше предела, по умолчанию 8°)
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "car.h"
#include "carparams.h"
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fl;
static ColWorld W;
int main(int argc, char **argv) {
  const char *name = argc > 1 ? argv[1] : "oblit_v"; float lim = argc > 2 ? (float)atof(argv[2]) : 8.f;
  memset(&fl, 0, sizeof fl); memcpy(fl.h.magic, "COL1", 4); fl.h.ox = fl.h.oz = -2000; fl.h.cell = 4000; fl.h.W = fl.h.H = 1; fl.h.ntri = fl.h.nref = 2;
  fl.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}};
  fl.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  fl.start[1] = 2; fl.refs[0] = 0; fl.refs[1] = 1; if (colInit(&W, &fl, sizeof fl)) return 99;
  Car c; CarParams p; carParamsFor(name, &p); if (getenv("WH_RANGE")) p.wheelieRange = (float)atof(getenv("WH_RANGE")); if (getenv("WH_Z")) p.wheelieZ = (float)atof(getenv("WH_Z")); if (getenv("WH_Y")) p.wheelieY = (float)atof(getenv("WH_Y")); printf("wheelieRange %.2f offY %.2f offZ %.2f\n", p.wheelieRange, p.wheelieY, p.wheelieZ); carInit(&c, &p, &W, 0, 0, 0, 0); CarInput in = {0, 0, 0, 0};
  for (int f = 0; f < 50; f++) carUpdate(&c, &W, &in, 1 / 50.f);
  float p0 = c.pitch, mx = 0; in.throttle = 1; printf("%s с места, газ 2,4 с: кадр тангаж° скорость\n", name);
  for (int f = 0; f < 120; f++) { carUpdate(&c, &W, &in, 1 / 50.f); float d = (c.pitch - p0) * 57.2958f; if (fabsf(d) > mx) mx = fabsf(d); if (f % 10 == 9) printf("  %3d %6.1f %5.1f\n", f + 1, d, c.v); }
  printf("пик тангажа %.1f° (предел %.1f°)\n%s\n", mx, lim, mx <= lim ? "PASS" : "FAIL");
  return mx <= lim ? 0 : 1;
}
