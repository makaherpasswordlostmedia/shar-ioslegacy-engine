// разбор L3/L5: порядок рисования кусков пропов — поразрядная сортировка ключом против прежнего qsort с функцией сравнения (флаги, текстура, номер): те же перестановки (Мак, только числа)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../viewer/propsort913.h"
static int F[1024], T[1024];
static const int *gF, *gT;
static int cmp(const void *a, const void *b) { int i = *(const unsigned short *)a, j = *(const unsigned short *)b; if (gF[i] != gF[j]) return gF[i] < gF[j] ? -1 : 1; if (gT[i] != gT[j]) return gT[i] < gT[j] ? -1 : 1; return i < j ? -1 : i > j; }
static unsigned rs = 99; static unsigned rnd(void) { rs = rs * 1664525u + 1013904223u; return rs >> 8; }
int main(void) {
  unsigned bad = 0, total = 0, fallbacks = 0; static const int flv[] = {0, 1, 4, 16, 0x100, 0x1000, 1 << 25, (1 << 25) | 1, 64, 128};
  for (int round = 0; round < 20000; round++) {
    int n = 1 + (int)(rnd() % 520), ntex = 1 + (int)(rnd() % 60);
    for (int i = 0; i < n; i++) { F[i] = flv[rnd() % 10]; T[i] = (int)(rnd() % (unsigned)ntex) - (round % 7 == 0 && !(rnd() % 9)); if (round % 5 == 0) T[i] = (int)(rnd() % 2047); }
    unsigned short ord[1024], ref[1024]; for (int i = 0; i < n; i++) ref[i] = (unsigned short)i;
    gF = F; gT = T; qsort(ref, (size_t)n, sizeof ref[0], cmp);
    int ok = pbSortKeys(F, T, n, ord);
#ifdef PROPSORT_BREAK
    if (ok && n > 3) { unsigned short t = ord[1]; ord[1] = ord[2]; ord[2] = t; }
#endif
    if (!ok) { fallbacks++; continue; }
    total++; if (memcmp(ord, ref, (size_t)n * sizeof ref[0])) bad++;
  }
  printf("PROPSORT checked=%u mismatched=%u fallbacks=%u\n", total, bad, fallbacks); return bad ? 1 : 0;
}
