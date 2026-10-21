// pitprobe — разбор глухой ямы (ночь 11.10): что вокруг точки (опоры по слоям, зоны DEATH, кольцо опор) и что делает машина с газом на 16 курсах.
//   pitprobe LEVEL PLAYER MSN x y z
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 7 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "usage\n"); return 2; }
  float x = (float)atof(argv[4]), y = (float)atof(argv[5]), z = (float)atof(argv[6]); bwNew(&W); const ColWorld *w = bwCol();
  printf("слои опоры в точке:"); { float yt = y + 30.f, g; int n = 0; while (n < 8 && colGround(w, x, z, yt, -1e6f, &g, 0)) { printf(" %.2f", g); yt = g - 0.05f; n++; } } printf("\n");
  printf("зоны DEATH (всего %u), ближе 80 м по xz:\n", w->ndeath);
  for (uint32_t i = 0; i < w->ndeath; i++) { const ColPad *d = &w->death[i]; float dx = d->c[0] - x, dz = d->c[2] - z; if (dx * dx + dz * dz > 80.f * 80.f) continue;
    printf("  %u %-8s центр %.1f %.1f %.1f полуразмеры %.1f %.1f %.1f оси[0] %.2f %.2f %.2f верх %.1f низ %.1f вершина-возврат %.1f %.1f %.1f\n", i, d->name, d->c[0], d->c[1], d->c[2], d->h[0], d->h[1], d->h[2], d->ax[0], d->ax[1], d->ax[2], d->c[1] + d->h[1], d->c[1] - d->h[1], d->apex[0], d->apex[1], d->apex[2]); }
  printf("опоры кольцом (высота ближайшей опоры не выше y+1.5, по 16 направлениям):\n");
  for (int r = 2; r <= 24; r += (r < 8 ? 2 : 4)) { printf("  r=%2d:", r); for (int a = 0; a < 16; a++) { float g; float px = x + sinf(a * 0.3926991f) * r, pz = z + cosf(a * 0.3926991f) * r;
      if (colGround(w, px, pz, y + 1.5f, -1e6f, &g, 0)) printf(" %6.1f", g - y); else printf("   ----"); } printf("\n"); }
  printf("езда с газом 2,5 с по 16 курсам: смещение м / v / касаний / удар о стену / осадка:\n");
  BotSnap S; bwSaveAlloc(&W, &S); { float gy; if (!colGround(w, x, z, y + 1.5f, -1e6f, &gy, 0)) gy = y; bwPlace(&W, x, gy + .3f, z, 0.f); for (int f = 0; f < 60; f++) bwStep(&W, 0, 0, 0); } bwSave(&W, &S);
  for (int h = 0; h < 16; h++) { bwLoad(&W, &S); bwPlace(&W, x, W.car.y, z, h * 0.3926991f); float wv = 0; int ct = 0;
    for (int f = 0; f < 150; f++) { bwStep(&W, GP_R, 0.f, 0.f); if (W.car.wallV > wv) wv = W.car.wallV; ct += W.car.contacts; }
    printf("  курс %2d: %.2f / %.2f / %d / %.1f / pen %.3f\n", h, hypotf(W.car.x - x, W.car.z - z), W.car.v, ct, wv, W.car.pen); }
  return 0;
}
