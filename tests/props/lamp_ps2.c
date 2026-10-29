// №488: фонарь L1 (проп 104, 1000 кг, ствол r 0,4) против PS2 (Стенд 16.10, ps2s_ram.py, famil_v, газ держит V, подход по оси): падение скорости сразу после касания
// (0,08 с) 2,5 / 3,75 / 6,4 м/с при 5,3 / 10,3 / 20,2 м/с (≈ 1,0 + 0,28·v). Порт: тот же заезд, максимум потери за 12 кадров после первого сбития. Допуск ±1,0 м/с.
// Красный: -DPROP_HEAVY_OLD=1 (тяжёлый проп скорость не гасит: потеря 0,15).
//   cc -std=c11 -O2 -DSKIN_HOST -I viewer tests/props/lamp_ps2.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c viewer/homer.c viewer/skin.c -lm
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"
static PropState *saved; static Props props; static ColWorld W; static Car car;
static int run(unsigned i, float dx, float dz, float v, float *loss) {
  PropDef *pd = &props.def[i]; float tx = pd->x + props.trunk[pd->type * 3], tz = pd->z + props.trunk[pd->type * 3 + 1], sx = tx - dx * 16.f, sz = tz - dz * 16.f, g;
  if (!colGround(&W, sx, sz, pd->y + 4.f, pd->y - 6.f, &g, 0)) return 0;
  memcpy(props.st, saved, props.ninst * sizeof(PropState)); props.havePreviousCar = 0;
  carInit(&car, NULL, &W, sx, g + 0.3f, sz, atan2f(dx, dz)); for (int k = 0; k < 30; k++) carUpdate(&car, &W, &(CarInput){0}, 1 / 60.f);
  carSetSpeed(&car, v); PropState *st = &props.st[i]; int tk = -1; float vc0 = v; *loss = 0;
  for (int fr = 0; fr < 6 * 60; fr++) {
    float vb = hypotf(car.vel[0], car.vel[2]); CarInput in = {0}; in.throttle = vb < v ? 1.f : 0.f;
    carUpdate(&car, &W, &in, 1 / 60.f); propsUpdate(&props, &W, &car, 1 / 60.f);
    if (tk < 0 && (!st->asleep || st->hidden)) { tk = fr; vc0 = vb; }
    if (tk >= 0 && fr - tk <= 12) { float vv = hypotf(car.vel[0], car.vel[2]); if (vc0 - vv > *loss) *loss = vc0 - vv; }
    if (tk >= 0 && fr - tk > 12) break;
  }
  return tk >= 0;
}
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *d = malloc(n); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n; if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co) || propsInit(&props, d + po, *(unsigned *)(d + po + 40))) return 2;
  saved = malloc(props.ninst * sizeof(PropState)); memcpy(saved, props.st, props.ninst * sizeof(PropState));
  const float V[3] = {5.3f, 10.3f, 20.2f}, ps2[3] = {2.5f, 3.75f, 6.4f}; int bad = 0;
  for (int k = 0; k < 3; k++) { float loss = 0; int ok = run(104, 0.f, -1.f, V[k], &loss) && fabsf(loss - ps2[k]) <= 1.0f; bad += !ok;
    printf("%s фонарь на %.1f м/с: потеря скорости %.2f, PS2 %.2f м/с\n", ok ? "ok  " : "FAIL", V[k], loss, ps2[k]); }
  printf("lamp_ps2: %s\n", bad ? "FAIL" : "PASS"); return bad;
}
