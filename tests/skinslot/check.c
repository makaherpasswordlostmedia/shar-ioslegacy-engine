// №914: хост-проверка перестановки слотов костей (viewer/skin.c skinSlotOpt): для каждой модели .chr из каталога — вершины каждой пачки, скиннинг на CPU со случайной палитрой
// (pos = Σ_k w_k/128 · M[bones[k]] · p, как GE) до и после перестановки: максимум расхождения; сумма весов; число загрузок матриц (слов) по порядку проходов до и после.
// cc -std=c11 -O1 -DSKIN_HOST -I viewer tests/skinslot/check.c viewer/skin.c -lm ; ./a.out DIR_С_CHR   (код 0 — расхождение <= 1e-4 и загрузок меньше; красный контроль: -DSKIN_SLOTOPT_BREAK)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dirent.h>
#include "skin.h"
static unsigned rs = 12345u; static float rnd(void) { rs = rs * 1664525u + 1013904223u; return (float)(rs >> 8) / 16777216.f; }
static void skinPos(const SkinModel *m, unsigned bi, unsigned v, const float pal[][12], float out[3]) {
  const SkinBatch *b = &m->b[bi]; const unsigned char *p = m->base + b->offVerts + (size_t)v * b->stride; const float *pos = (const float *)(p + b->stride - 12);
  out[0] = out[1] = out[2] = 0.f;
  for (unsigned k = 0; k < b->nb; k++) { float w = p[k] / 128.f; const float *M = pal[b->bones[k]];
    for (int r = 0; r < 3; r++) out[r] += w * (M[r] * pos[0] + M[3 + r] * pos[1] + M[6 + r] * pos[2] + M[9 + r]); }
}
int main(int argc, char **argv) {
  if (argc < 2) return 2; DIR *d = opendir(argv[1]); if (!d) return 2; struct dirent *e; unsigned nm = 0; double worst = 0; unsigned ub = 0, ua = 0; int bad = 0; unsigned nver = 0;
  while ((e = readdir(d))) {
    size_t l = strlen(e->d_name); if (l < 5 || strcmp(e->d_name + l - 4, ".chr")) continue;
    char path[512]; snprintf(path, sizeof path, "%s/%s", argv[1], e->d_name);
    skinSetSlotOpt(0); SkinModel *a = skinLoad(path); skinSetSlotOpt(1); SkinModel *b = skinLoad(path); if (!a || !b) continue;
    if (a->h->nBatches != b->h->nBatches) { printf("%s: число пачек разное\n", e->d_name); bad = 1; continue; }
    static float pal[64][12]; for (int j = 0; j < 64; j++) for (int k = 0; k < 12; k++) pal[j][k] = rnd() * 2.f - 1.f;
    double mw = 0;
    for (unsigned i = 0; i < a->h->nBatches; i++) { unsigned sv = skinBatchStoredVerts(&a->b[i]); if (a->b[i].nb != b->b[i].nb || sv != skinBatchStoredVerts(&b->b[i])) { bad = 1; continue; }
      for (unsigned v = 0; v < sv; v++) { float pa[3], pb[3]; skinPos(a, i, v, pal, pa); skinPos(b, i, v, pal, pb); nver++;
        for (int r = 0; r < 3; r++) { double dd = fabs(pa[r] - pb[r]) / (1.0 + fabs(pa[r])); if (dd > mw) mw = dd; } } }
    if (mw > worst) worst = mw; nm++;
  }
  closedir(d); ub = skinSlotBefore; ua = skinSlotAfter;
  printf("моделей %u, вершин %u, наибольшее относительное расхождение скиннинга %.2e; загрузок матриц костей за три прохода (сумма по моделям): было %u, стало %u (%.0f %%)\n", nm, nver, worst, ub, ua, ub ? 100.0 * ua / ub : 0.0);
  int ok = nm > 0 && !bad && worst <= 1e-4 && ua < ub; printf("%s\n", ok ? "PASS" : "FAIL"); return ok ? 0 : 1;
}
