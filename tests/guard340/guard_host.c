// Правка Роба 340 (гейт tests/guard340/gate.sh): настоящий код viewer/ge_guard.h на Маке.
// stdin, строки: «T tvx tvy zn x0 y0 z0 x1 y1 z1 x2 y2 z2» (треугольник в осях камеры) -> «risk n x y z …» (многоугольник среза, оси камеры);
//                «B tvx tvy zn x0 y0 z0 … x7 y7 z7» (бокс, 8 углов) -> «risk».
// Сборка с -DGG_OLD — прежнее (как flag ggold 1): риск всегда 0, ничего не режется (красный контроль).
#include <stdio.h>
#include "ge_guard.h"

int main(void) {
  char m[4];
  while (scanf("%3s", m) == 1) {
    GgCam k; if (scanf("%f %f %f", &k.tvx, &k.tvy, &k.zn) != 3) return 1;
    if (m[0] == 'T') {
      GgV v[3] = {{{0}}};
      for (int i = 0; i < 3; i++) if (scanf("%f %f %f", &v[i].c[0], &v[i].c[1], &v[i].c[2]) != 3) return 1;
      for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) v[i].l[j] = v[i].c[j];
#ifdef GG_OLD
      int r = 0;
#else
      int r = ggRisk(&v[0], &v[1], &v[2], &k);
#endif
      printf("%d", r);
      if (r) { GgV o[GG_MAXV]; int n = ggCut(&v[0], &v[1], &v[2], &k, o); printf(" %d", n); for (int i = 0; i < n; i++) printf(" %.7g %.7g %.7g", o[i].c[0], o[i].c[1], o[i].c[2]); }
      printf("\n");
    } else {
      float c[8][3];
      for (int i = 0; i < 8; i++) if (scanf("%f %f %f", &c[i][0], &c[i][1], &c[i][2]) != 3) return 1;
#ifdef GG_OLD
      printf("0\n");
#else
      printf("%d\n", ggBoxRisk((const float (*)[3])c, &k));
#endif
    }
  }
  return 0;
}
