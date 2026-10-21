// landtest — №536: посадка после прыжка не наносит урона (LAND_DAMAGE_OLD=1 в сборке — прежнее), лобовой удар в стену — как прежде.
//   landtest LEVEL PLAYER MSN TARGETS   сценарии: падение с 8 м (0 и 20 м/с), заезды на зоны прыжка (jumpzone*) с 8 курсов, лобовой в стену 25 м/с
//   печатает по строке на сценарий и итог "ИТОГ посадки: макс. урон X (сценариев N), стена: урон Y"; код выхода 1, если урон посадки > 0.001
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
extern float carDmgSrc[3];
static BotWorld W;
typedef struct { float x, z; char name[40]; } Z;
static float run(float x, float z, float h, float hgt, float v, int frames, int *air, float *vmax) {
  float gy; if (!colGround(bwCol(), x, z, 300.f, -1e6f, &gy, 0)) return -1.f;
  bwPlace(&W, x, gy + .3f + hgt, z, h); for (int f = 0; f < (hgt > 0 ? 1 : 60); f++) bwStep(&W, 0, 0.f, 0.f);
  memset(carDmgSrc, 0, sizeof carDmgSrc); W.car.damage = 0.f; W.car.destroyed = 0; carSetSpeed(&W.car, v); *air = 0; *vmax = 0;
  float d0 = 0.f, dl = 0.f; int landed = -1;   // урон считаем только в окне посадки: от первого касания после полёта и 20 кадров дальше
  for (int f = 0; f < frames; f++) {
    float dBefore = W.car.damage; bwStep(&W, v > 1.f ? GP_R : 0, 0.f, 0.f);
    int inAir = !W.car.grounded && W.car.y > gy + 1.f;
    if (inAir) { (*air)++; if (landed < 0) d0 = W.car.damage; }
    else if (*air >= 20 && landed < 0) { landed = f; d0 = dBefore; }
    if (fabsf(W.car.v) > *vmax) *vmax = fabsf(W.car.v);
    if (landed >= 0 && f == landed + 20) { dl = W.car.damage - d0; break; }
  }
  return landed >= 0 ? dl : W.car.damage;
}
int main(int argc, char **argv) {
  if (argc < 5 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "usage: landtest LEVEL PLAYER MSN TARGETS\n"); return 2; }
  bwNew(&W); static Z z[64]; int nz = 0; FILE *f = fopen(argv[4], "r"); char ln[256];
  while (f && fgets(ln, sizeof ln, f) && nz < 64) { char k[16], nm[40]; float x, y, zz, r; if (sscanf(ln, "%15s %39s %f %f %f %f", k, nm, &x, &y, &zz, &r) == 6 && !strcmp(k, "ramp") && !strncmp(nm, "jumpzone", 8)) { z[nz].x = x; z[nz].z = zz; snprintf(z[nz].name, 40, "%s", nm); nz++; } }
  float worst = 0.f, gsum = 0.f; int nsc = 0, air; float vm;
  float sx = 220.f, sz = 172.f;   // спавн L1: ровная площадка
  for (int k = 0; k < 4; k++) { float hh = k < 2 ? 8.f : 15.f; float d = run(sx, sz, 1.5708f, hh, (k & 1) * 12.f, 360, &air, &vm); printf("падение с %.0f м, v0 %2d: урон %.3f (днище %.3f, стена %.3f) разбита %d\n", hh, (k & 1) * 12, d, carDmgSrc[0], carDmgSrc[1], W.car.destroyed); gsum += carDmgSrc[0]; nsc++; }
  for (int i = 0; i < nz; i++) for (int a = 0; a < 8; a++) {
    float ang = a * .785398f, x0 = z[i].x - sinf(ang) * 40.f, z0 = z[i].z - cosf(ang) * 40.f;
    float d = run(x0, z0, ang, 0.f, 6.f, 600, &air, &vm); if (d < 0) continue;
    if (air < 20) continue;   // не взлетела — не прыжок
    printf("%s курс %d: в воздухе %d кадров, v макс %.1f, урон %.3f (днище о опору %.3f, стена/предмет %.3f, машина %.3f)\n", z[i].name, a * 45, air, vm, d, carDmgSrc[0], carDmgSrc[1], carDmgSrc[2]); if (d > worst) worst = d; gsum += carDmgSrc[0]; nsc++;
  }
  // лобовой в стену: 16 лучей от спавна, берём первый с стеной на 25–70 м
  float wall = -1.f;
  for (int k = 0; k < 16 && wall < 0.f; k++) {
    float a = k * .3926991f, g; colGround(bwCol(), sx, sz, 300.f, -1e6f, &g, 0);
    float p0[3] = {sx, g + .8f, sz}, p1[3] = {sx + sinf(a) * 90.f, g + .8f, sz + cosf(a) * 90.f}; float fr = colRayFrac(bwCol(), p0, p1, 0), dd = 90.f * fr;
    if (dd > 30.f && dd < 80.f) { wall = run(sx, sz, a, 0.f, 25.f, 400, &air, &vm); printf("лобовой в стену (курс %.0f°, %.0f м): урон %.3f\n", a * 57.2958f, dd, wall); }
  }
  printf("ИТОГ посадки: урон днищем о опору за все прыжки %.3f (сценариев %d), стена: урон %.3f\n", gsum, nsc, wall);
  return gsum > 0.001f ? 1 : 0;
}
