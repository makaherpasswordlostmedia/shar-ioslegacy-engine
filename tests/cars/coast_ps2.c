// №388: накат famil_v (газ отпущен полностью, без тормоза, руль по центру) против PS2 (Стенд 16.10, build/ps2stend/out/famil_v/coast_V10/20/28.tsv,
// ровная улица L1, 50 к/с, 3 с): скорость после лага отпуска газа (0,2 с) 9,98 / 19,89 / 27,62 → через 2,76 с PS2 3,39 / 12,45 / 18,31 м/с.
// Порт на ровной площадке: та же начальная скорость, газ 0, те же 2,76 с. Допуск ±0,6 м/с (на 10 м/с порт у обеих машин останавливается чуть позже PS2: +0,2…+0,55). Красный: -DCAR_COAST_LIN=0 (сопротивление по TopSpeed без газа:
// 28 м/с теряет 7,7 м/с²).   cc -std=c11 -O2 -I viewer tests/cars/coast_ps2.c viewer/car.c viewer/col.c -lm
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fl;
int main(void) {
  memset(&fl, 0, sizeof fl); memcpy(fl.h.magic, "COL1", 4); fl.h.ox = fl.h.oz = -2000; fl.h.cell = 4000; fl.h.W = fl.h.H = 1; fl.h.ntri = fl.h.nref = 2;
  fl.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}}; fl.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  fl.start[1] = 2; fl.refs[0] = 0; fl.refs[1] = 1;
  ColWorld w; if (colInit(&w, &fl, sizeof fl)) return 2;
  // PS2 после лага отпуска газа (первые 10 кадров скорость почти не падает): v10 → конец через 2,76 с
  const struct { const char *car; float v0[3], end[3]; } R[2] = {
    {"famil_v", {9.98f, 19.89f, 27.62f}, {3.39f, 12.45f, 18.31f}},
    {"bart_v", {10.94f, 20.79f, 28.05f}, {3.96f, 13.09f, 19.00f}}};   // bart_v (Стенд, coast_V10/20/28 той же серии): накат общий, не зависит от массы и тяги
  int bad = 0;
  for (int m = 0; m < 2; m++) for (int k = 0; k < 3; k++) {
    CarParams p; carParamsFor(R[m].car, &p); Car c; carInit(&c, &p, &w, 0, 0, 0, 0);
    for (int i = 0; i < 50; i++) carUpdate(&c, &w, &(CarInput){0}, 1.f / 50);
    carSetSpeed(&c, R[m].v0[k]);
    float v0 = c.v; for (int i = 0; i < 138; i++) carUpdate(&c, &w, &(CarInput){0}, 1.f / 50);
    int ok = fabsf(c.v - R[m].end[k]) <= 0.6f; bad += !ok;
    printf("%s %-7s накат %.1f м/с за 2,76 с: порт %.2f, PS2 %.2f (замедление порта %.2f, PS2 %.2f м/с²)\n", ok ? "ok  " : "FAIL", R[m].car, v0, c.v, R[m].end[k], (v0 - c.v) / 2.76f, (R[m].v0[k] - R[m].end[k]) / 2.76f);
  }
  printf("coast_ps2: %s\n", bad ? "FAIL" : "PASS"); return bad;
}
