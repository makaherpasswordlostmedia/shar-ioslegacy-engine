// №406/В102 (Стенд 16.10, ps2s_steer.py, PS2 L1, подмена машины): скользящий удар о длинную вертикальную стену на 10 м/с (газ держит 10, руль держит курс на стену) под 35°:
// schoolbu 10→2,7 м/с, пик крена 13,6°, выше 8° 28 кадров, выше 15° 0; marge_v пик 16,0°, выше 8° 40 кадров, выше 15° 3 кадра, на два колеса не встаёт.
// Порт: плоская площадка и стена x = 30 (два вертикальных треугольника). Печатает по машине: пик крена, кадры (50 к/с) с креном > 8° / > 15°, кадры на ≤ 2 колёсах,
// колёс на земле через 0,3 с после удара, скорость после. Гейт (marge_v, schoolbu): колёс ≥ 3 через 0,6 с, пик ≤ 18°, на ≤ 2 колёсах не более 14 кадров (прежнее CAR_HITY_OLD=1: 22 / 15 кадров, нос −10°).
//   cc -std=c11 -O2 -I viewer tests/cars/wallslide.c viewer/car.c viewer/col.c -lm   ./a.out [машина …]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "carparams.h"
static struct { ColHdr h; ColTri t[4]; unsigned start[2], refs[4]; } fl;
int main(int argc, char **argv) {
  memset(&fl, 0, sizeof fl); memcpy(fl.h.magic, "COL1", 4); fl.h.ox = fl.h.oz = -2000; fl.h.cell = 4000; fl.h.W = fl.h.H = 1; fl.h.ntri = 4; fl.h.nref = 4;
  fl.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}}; fl.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  fl.t[2] = (ColTri){{30, -5, -2000}, {30, 40, 2000}, {30, 40, -2000}, {-1, 0, 0}}; fl.t[3] = (ColTri){{30, -5, -2000}, {30, -5, 2000}, {30, 40, 2000}, {-1, 0, 0}};   // стена x=30, нормаль к −x (к машине)
  fl.start[1] = 4; fl.refs[0] = 0; fl.refs[1] = 1; fl.refs[2] = 2; fl.refs[3] = 3;   // одна ячейка: start[0]=0, start[1]=4 (концы)
  ColWorld w; if (colInit(&w, &fl, sizeof fl)) return 2;
  const char *list[8]; int n = 0; if (argc > 1) for (int i = 1; i < argc && n < 8; i++) list[n++] = argv[i]; else { list[0] = "marge_v"; list[1] = "schoolbu"; list[2] = "famil_v"; list[3] = "bart_v"; list[4] = "cbone"; list[5] = "minivana"; n = 6; }
  int bad = 0;
  for (int m = 0; m < n; m++) {
    CarParams p; carParamsFor(list[m], &p); Car c; float ang = 35.f * 0.0174533f;
    // курс на стену под 35° к нормали: нормаль −x, значит едем на +x с поворотом на ang в сторону z
    float h = 1.5707963f - ang;   // h: 90° = +x; меньше = к +z
    carInit(&c, &p, &w, 0, 0, 0, h); for (int i = 0; i < 50; i++) carUpdate(&c, &w, &(CarInput){0}, 1.f / 50);
    carSetSpeed(&c, 10.f);
    int fr8 = 0, fr15 = 0, two = 0, hitF = -1; float peak = 0, vAfter = 0; int wheels03 = 4;
    for (int f = 0; f < 250; f++) {
      CarInput in = {0}; in.throttle = c.v < 10.f ? 1.f : 0.f;
      carUpdate(&c, &w, &in, 1.f / 50);
      float roll = fabsf(c.roll) * 57.2958f; if (hitF >= 0) { if (roll > peak) peak = roll; fr8 += roll > 8.f; fr15 += roll > 15.f; two += c.wheels <= 2; if (f - hitF == 30) { wheels03 = c.wheels; } if (f - hitF == 25) vAfter = c.v; }
      if (hitF < 0 && (c.contacts || c.hitSpeed > 0.5f || c.x > 28.f)) hitF = f;
    }
    int isTall = !strcmp(list[m], "marge_v") || !strcmp(list[m], "schoolbu");
    int ok = !isTall || (wheels03 >= 3 && peak <= 18.f && two <= 14); bad += !ok;
    printf("%s %-9s удар на кадре %d: пик крена %.1f°, >8° %d кадров, >15° %d, на ≤2 колёсах %d кадров, колёс через 0,6 с %d, v после 0,5 с %.1f (PS2: schoolbu 13,6°/28/0, marge_v 16,0°/40/3)\n", ok ? "ok  " : "FAIL", list[m], hitF, peak, fr8, fr15, two, wheels03, vAfter);
  }
  printf("wallslide: %s\n", bad ? "FAIL" : "PASS"); return bad;
}
