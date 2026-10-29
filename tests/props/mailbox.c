// Почтовый ящик (В138, PS2-Наблюдатель b2_mail): удар машины ~11.3 м/с по ящику ~125 кг. PS2: ящик ~10 м/с вдоль удара, машина
// теряет 1.19 м/с за 0.04 с, ящик валится на бок (up-ось горизонтальна), путь центра 11.3 м, до покоя 1.84 с.
//   cc ... tests/props/mailbox.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm && ./a.out LEVEL.shr
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"
static Props props; static ColWorld W; static Car car;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = malloc(n); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co) || propsInit(&props, d + po, *(unsigned *)(d + po + 40))) return 2;
  float tx = argc > 2 ? atof(argv[2]) : 214.573f, tz = argc > 3 ? atof(argv[3]) : 158.354f; int best = -1; float bd = 1e9f;
  for (unsigned i = 0; i < props.ninst; i++) { float dd = hypotf(props.def[i].x - tx, props.def[i].z - tz); if (dd < bd) { bd = dd; best = (int)i; } }
  PropDef *pd = &props.def[best]; PropType *ty = &props.types[pd->type];
  printf("ящик %d тип %u в (%.2f %.2f %.2f) от цели %.1f м: радиус %.2f halfH %.2f масса %.0f, коробка %.2f %.2f %.2f\n", best, pd->type, pd->x, pd->y, pd->z, bd,
         ty->radius, ty->halfH, ty->mass, props.st[best].hx, props.st[best].hy, props.st[best].hz);
  float dirx = argc > 4 ? atof(argv[4]) : -0.443f, dirz = argc > 5 ? atof(argv[5]) : 0.896f, l = hypotf(dirx, dirz); dirx /= l; dirz /= l;
  float off = argc > 6 ? atof(argv[6]) : 0.f;   // боковое смещение машины, м (вправо по ходу)
  float sx = pd->x - dirx * 14.f + dirz * off, sz = pd->z - dirz * 14.f - dirx * off, g;
  if (!colGround(&W, sx, sz, pd->y + 5.f, pd->y - 10.f, &g, 0)) { printf("нет земли на старте\n"); return 1; }
  carInit(&car, NULL, &W, sx, g + 1.f, sz, atan2f(dirx, dirz));
  for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&car, &W, &in, 1 / 60.f); }
  carSetSpeed(&car, 11.28f); props.havePreviousCar = 0;
  PropState *st = &props.st[best]; float x0 = st->x, z0 = st->z, vmax = 0.f, loss = 0.f, tSleep = -1.f, tk = -1.f, vcar0 = 0.f; int kicked = 0;
  for (int fr = 0; fr < 6 * 60; fr++) {
    CarInput in = {0}; float vb = hypotf(car.vel[0], car.vel[2]); in.throttle = (!kicked && vb < 11.28f) ? 1.f : 0.f;
    carUpdate(&car, &W, &in, 1 / 60.f); propsUpdate(&props, &W, &car, 1 / 60.f);
    float t = (fr + 1) / 60.f, vh = hypotf(st->vel[0], st->vel[2]);
    if (!kicked && !st->asleep) { kicked = 1; tk = t; vcar0 = vb; }
    if (kicked && t - tk < 0.045f && t - tk > 0.02f) loss = vcar0 - hypotf(car.vel[0], car.vel[2]);
    if (vh > vmax) vmax = vh;
    if (kicked && tSleep < 0 && st->asleep) tSleep = t - tk;
    }
  float vend = hypotf(car.vel[0], car.vel[2]); R:;
  float R[3][3]; extern void quatToR(const float *, float[3][3]);
  printf("толчок: ящик vmax %.2f м/с; путь центра %.2f м; до покоя %.2f с; up-ось y %.2f\n", vmax, hypotf(st->x - x0, st->z - z0), tSleep, 0.f);
  printf("машина: до %.2f, потеря за 0.04 с %.2f; PS2: ящик ~10, путь 11.3, 1.84 с, потеря 1.19 за 0.04 с\n", vcar0, loss);
  (void)R; (void)loss; return 0;
}
