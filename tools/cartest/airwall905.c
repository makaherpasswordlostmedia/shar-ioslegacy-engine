// Гейт правки 905 (L1 H4-6): машина в полёте над ямой у подножия горы не должна упираться в «стену до неба» (забор Wall с верхом +1e6,
// принятый за край карты, tools/psp_export.py FENCE_CLIFF_OLD). Ставим машину в воздух на высоте Y над точкой (X, Z) курсом на стену, скорость V м/с, без управления,
// считаем кадры с контактом типа 3 (отрезок забора) и силой удара > 3 м/с, пока машина выше TOP м над землёй под ней.
// usage: airwall905 level.shr X Z heading V Y [секунд=2] ; выход: строка RESULT hits=N maxHit=H, код 0 — стены нет, 1 — упёрлась
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"
extern int colDebug;
static ColWorld w;
static int loadCol(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) return -1; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return -1; fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96);
  unsigned end = n; if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff);
  return colInit(&w, cm, end - colOff);
}
int main(int argc, char **argv) {
  if (argc < 7 || loadCol(argv[1])) { puts("usage: airwall905 level.shr X Z heading V Y [sec]"); return 2; }
  float x = atof(argv[2]), z = atof(argv[3]), h = atof(argv[4]), v = atof(argv[5]), y0 = atof(argv[6]), secs = argc > 7 ? atof(argv[7]) : 2.f;
  static Car car; float g = 0; colGround(&w, x, z, 200, -1e6f, &g, 0);
  carInit(&car, NULL, &w, x, g, z, h);
  for (int i = 0; i < 30; i++) { CarInput in = {0}; carUpdate(&car, &w, &in, 1 / 60.f); }
  car.y = y0; car.vy = 0; carSetSpeed(&car, v);
  int hits = 0; float maxHit = 0, dt = 1 / 60.f, hitY = -1;
  for (int fr = 0; fr < secs * 60; fr++) {
    CarInput in = {0}; carUpdate(&car, &w, &in, dt);
    if (car.grounded) break;   // сел — дальше обычная езда, не полёт
    for (int k = 0; k < car.contacts; k++) if (car.ctype[k] == 3 && car.hitSpeed > 3.f) { hits++; if (!hitY || hitY < 0) hitY = car.y; if (car.hitSpeed > maxHit) maxHit = car.hitSpeed; break; }
  }
  printf("RESULT hits=%d maxHit=%.1f hitY=%.1f end %.1f %.1f %.1f\n", hits, maxHit, hitY, car.x, car.y, car.z);
  return hits ? 1 : 0;
}
