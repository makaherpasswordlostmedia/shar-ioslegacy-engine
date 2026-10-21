// Правка 252: NaN в состоянии машины (как после 0/0 в физике, когда ловушки FPU выключены — viewer/fpuguard.h). Мир ботов на
// Маке (тот же viewer/car.c, что EBOOT): машина разгоняется 2 с по спавну L1 (надёжные места пишутся), скорости дают NaN, ещё 1 с.
// Новое: машина снова в числах, на надёжном месте, carNanFixes >= 1. Прежнее (-DCAR_NAN_OLD): машина «нигде» (NaN) — выход 1.
//   nan_host LEVEL HOMER   -> строка NANHOST …; выход 0 — машина конечна
#include <stdio.h>
#include <math.h>
#include "world.h"
int main(int argc, char **argv) {
  if (argc < 3 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "нет данных\n"); return 2; }
  static BotWorld w; if (bwNew(&w)) return 2;
  for (int f = 0; f < 120; f++) bwStep(&w, 0x4000, 0.f, 0.f);   // газ (cross) 2 с
  float x0 = w.car.x, z0 = w.car.z;
  w.car.vel[0] = NAN; w.car.w[1] = NAN;                         // как NaN из 0/0
  for (int f = 0; f < 60; f++) bwStep(&w, 0, 0.f, 0.f);
  int fin = isfinite(w.car.x) && isfinite(w.car.y) && isfinite(w.car.z) && isfinite(w.car.vel[0]) && isfinite(w.car.q[0]);
  printf("NANHOST fixes=%u finite=%d car=%.2f,%.2f,%.2f (до NaN %.2f,%.2f)\n", carNanFixes, fin, w.car.x, w.car.y, w.car.z, x0, z0);
  return fin ? 0 : 1;
}
