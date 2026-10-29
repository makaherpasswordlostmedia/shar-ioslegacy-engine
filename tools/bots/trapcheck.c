// trapcheck — настоящая ловушка или тупик бота (разбор ночи 11.10, «КОЛЛИЗИИ_НОЧЬ_РАЗБОР»): для каждого места из списка машина ставится
// на 16 курсов; как у inspector/explorer (8 заходов по 2.5 с: газ, назад, с рулём) — «не выезжает»; тогда расширенный поиск выхода,
// как мог бы водитель: три фазы по 1.2 с из шести действий (газ/назад × руль −1/0/1) = 216 цепочек; выехала дальше 8 м от места — не
// ловушка (тупик бота, объезжается трёхточечным разворотом). Тот же мир, что EBOOT (tools/bots/world.c), CPU Мака, без эмулятора.
//   trapcheck LEVEL PLAYER POINTS   (POINTS: x y z на строку)
// Строка: P<TAB>номер<TAB>x y z<TAB>курсов с «не выезжает» (из 16)<TAB>курсов, где не выехала и расширенным поиском<TAB>лучший выход м<TAB>
//   маска курсов без выхода (бит h — курс h·22.5°)<TAB>маска курсов, где кузов в точке уже внутри геометрии (осадка > 0.15 м: поза недопустима, не ловушка)<TAB>маска курсов с осадкой > 0.02 м (машину держит «заклинено»: car.c PEN_REVERT отменяет подшаг, если после выталкивания остались > 2 см)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W; static BotSnap S0, P0, P1;
static int basicFree(float x0, float z0) {
  static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
  bwSave(&W, &P0);
  for (int d = 0; d < 8; d++) {
    bwLoad(&W, &P0);
    for (int f = 0; f < 150; f++) { unsigned bt = d < 3 ? GP_R : d < 6 ? GP_L : (f < 45 ? GP_L : GP_R); float ax = d >= 6 && f < 45 ? -steer[d] : steer[d]; bwStep(&W, bt, ax, 0.f); }
    if (gameOnFoot(&W.G) || W.car.destroyed || hypotf(W.car.x - x0, W.car.z - z0) > 3.f) return 1;
  }
  return 0;
}
static float extFree(float x0, float z0) {
  bwSave(&W, &P1); float best = 0.f;
  for (int s = 0; s < 216; s++) {
    int a0 = s % 6, a1 = s / 6 % 6, a2 = s / 36;
    bwLoad(&W, &P1);
    for (int ph = 0; ph < 3; ph++) { int a = ph == 0 ? a0 : ph == 1 ? a1 : a2;
      unsigned bt = (a / 3) ? GP_L : GP_R; float ax = (a % 3) - 1.f;
      for (int f = 0; f < 72; f++) bwStep(&W, bt, ax, 0.f); }
    if (gameOnFoot(&W.G) || W.car.destroyed) continue;
    float d = hypotf(W.car.x - x0, W.car.z - z0); if (d > best) best = d; if (best > 8.f) return best;
  }
  return best;
}
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "trapcheck LEVEL PLAYER POINTS\n"); return 2; }
  bwNew(&W); bwSaveAlloc(&W, &S0); bwSaveAlloc(&W, &P0); bwSaveAlloc(&W, &P1); bwSave(&W, &S0);
  FILE *f = fopen(argv[3], "r"); if (!f) return 2; char ln[256]; float x, y, z; int n = 0;
  while (fgets(ln, sizeof ln, f)) {
    if (sscanf(ln, "%f %f %f", &x, &y, &z) != 3) continue;
    int basic = 0, ext = 0, mask = 0, imask = 0, emask = 0; float bestExit = 0.f;
    for (int h = 0; h < 16; h++) {
      bwLoad(&W, &S0); bwPlace(&W, x, y + .3f, z, h * 0.3926991f);
      for (int k = 0; k < 30; k++) bwStep(&W, 0, 0, 0);
      float x0 = W.car.x, z0 = W.car.z;
      { CarBox b; memset(&b, 0, sizeof b); float a = h * 0.3926991f; b.x = x0; b.z = z0; b.fx = sinf(a); b.fz = cosf(a); b.hw = 1.10f; b.hl = 2.675f; b.y = W.car.y; b.lo = 0.35f; b.hi = 1.6f;
        colProbeCar(bwCol(), &b); if (b.maxDepth > .15f) imask |= 1 << h; if (b.maxDepth > .02f) emask |= 1 << h; }
      if (basicFree(x0, z0)) continue;
      basic++;
      float e = extFree(x0, z0); if (e > bestExit) bestExit = e; if (e <= 8.f) { ext++; mask |= 1 << h; }
    }
    printf("P\t%d\t%.1f %.1f %.1f\t%d\t%d\t%.1f\t%d\t%d\t%d\n", n++, x, y, z, basic, ext, bestExit, mask, imask, emask); fflush(stdout);
  }
  return 0;
}
