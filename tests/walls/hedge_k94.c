// Изгородь K9-4 напротив дома (ДОБИВКА п. 11, решение Роба 09.10 «изгороди как в оригинале»): повтор проб PS2 физикой порта.
// Настоящие carUpdate/col (viewer/car.c, viewer/col.c), уровень build/level.shr; PS2 не запускается.
// Вход (tests/walls/hedge_k94.py): строки «id x y z_ps2 курс_град vx vy vz_ps2 режим кадров vt»
//   режим pulse — как tools/twins/hedge.py (v200_hedge): с кадра 40 газ, пока горизонтальная скорость < vt
//   режим ram   — как tools/twins/boom.py (v199_boom) от позы за ~0,3 с до удара: газ, пока не «удар» (скорость была > 6 и
//                 упала ниже 0,6 от наибольшей, не раньше 30 кадров), потом 40 кадров без газа
// Кадр — единица счётчика PS2 (1/50 с, tools/twins/placement.py ORIG_FPS); шаг порта 0,02 с, как tests/walls/hedge30.c.
// Выход: на каждый второй кадр «id кадр x y z_ps2 v курс_град» в осях PS2 (z_ps2 = −z порта).
#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/car.c"
int main(int argc, char **argv) {
  if (argc != 3) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long sz = ftell(f); rewind(f); unsigned char *d = malloc(sz);
  if (!d || fread(d, 1, sz, f) != (size_t)sz) return 2; fclose(f);
  unsigned co, po, pv; memcpy(&co, d + 92, 4); memcpy(&po, d + 96, 4); memcpy(&pv, d + 88, 4); unsigned end = sz;
  if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  ColWorld W; if (colInit(&W, d + co, end - co)) return 2;
  if (getenv("HEDGE_K94_NO_HEDGE")) {   // самопроверка гейта (не поведение игры): изгородь K9-4 — ящики и лежачие капсулы
    int n = 0;                          // вдоль линии z порта 146,97 (common_gens10/…, x 203–243) уводим на 1 км вниз
    for (unsigned i = 0; i < W.nbox; i++) { ColBox *b = (ColBox *)&W.box[i];
      if (fabsf(b->c[2] - 146.97f) < 0.5f && b->c[0] > 200.f && b->c[0] < 246.f) { b->c[1] -= 1000.f; n++; } }
    for (unsigned i = 0; i < W.ncyl; i++) { ColCyl *c = (ColCyl *)&W.cyl[i];
      if (fabsf(c->c[2] - 146.97f) < 0.5f && c->c[0] > 200.f && c->c[0] < 246.f) { c->c[1] -= 1000.f; n++; } }
    fprintf(stderr, "без изгороди: убрано примитивов %d\n", n);
  }
  f = fopen(argv[2], "r"); if (!f) return 2;
  char id[96], mode[16]; float x, y, z, hd, vx, vy, vz, vt; int frames;
  while (fscanf(f, "%95s %f %f %f %f %f %f %f %15s %d %f", id, &x, &y, &z, &hd, &vx, &vy, &vz, mode, &frames, &vt) == 11) {
    if (frames < 1 || frames > 4000) return 2;
    CarParams p; carParamsFor("famil_v", &p); Car c;
    float h = 3.14159265f - hd * 0.01745329f;                 // курс порта = π − курс PS2 (tools/twins/common.py port_h_of_yaw)
    carInit(&c, &p, &W, x, y, -z, h);
    c.vel[0] = vx; c.vel[1] = vy; c.vel[2] = -vz; syncOut(&c);
    int ram = !strcmp(mode, "ram"), hit = -1; float vmax = 0.f;
    for (int k = 0; k <= frames; k++) {
      float v = hypotf(c.vel[0], c.vel[2]);
      if (k % 2 == 0) printf("%s %d %.4f %.4f %.4f %.4f %.3f\n", id, k, c.x, c.y, -c.z, v, 180.f - c.h * 57.2957795f);
      if (k == frames) break;
      CarInput in = {0};
      if (!ram) in.throttle = k >= 40 && v < vt ? 1.f : 0.f;
      else {
        if (hit < 0) { vmax = fmaxf(vmax, v); if (vmax > 6.f && v < 0.6f * vmax && k > 2) hit = k; }
        in.throttle = hit < 0 ? 1.f : 0.f;
        if (hit >= 0 && k > hit + 40) { printf("%s %d %.4f %.4f %.4f %.4f %.3f\n", id, k, c.x, c.y, -c.z, v, 180.f - c.h * 57.2957795f); break; }
      }
      carUpdate(&c, &W, &in, .02f);
    }
  }
  fclose(f); colFree(&W); free(d); return 0;
}
