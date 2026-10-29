// Проверка матриц перед видеочипом (viewer/geguard.h, правки 259/252)
#undef sceGuSetMatrix   // -include geguard.h уже подменил имена: здесь — настоящие вызовы (иначе рекурсия)
#undef sceGuBoneMatrix
#define GEGUARD_IMPL
#ifndef GEGUARD_HOST
#include <pspgu.h>
#endif
#include <string.h>
#include "geguard.h"
volatile unsigned geGuardHits;
int geFinite(float a) { unsigned u; memcpy(&u, &a, 4); return ((u >> 23) & 0xffu) < 127u + 24u; }
#ifdef GEGUARD_OLD
int geMatOk(const float *f, int n) { (void)f; (void)n; return 1; }   // красный контроль: как до правки — любая матрица уходит в GE
#else
int geMatOk(const float *f, int n) { for (int i = 0; i < n; i++) if (!geFinite(f[i])) return 0; return 1; }
#endif
#ifndef GEGUARD_HOST
static const ScePspFMatrix4 geZero = {{0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 1}};
void geSetMatrixSafe(int type, const ScePspFMatrix4 *m) {
  if (m && geMatOk(&m->x.x, 16)) { sceGuSetMatrix(type, m); return; }
  geGuardHits++; sceGuSetMatrix(type, &geZero);
}
void geBoneMatrixSafe(unsigned int index, const ScePspFMatrix4 *m) {
  if (m && geMatOk(&m->x.x, 16)) { sceGuBoneMatrix(index, m); return; }
  geGuardHits++; sceGuBoneMatrix(index, &geZero);
}
#endif
