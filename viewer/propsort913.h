// Разбор L3/L5 (тур TEST55, x_props / sp_flush 1,15 мс PSP на причале L3): propFlush сортировал до 512 кусков пропов и стейтпропов через qsort с функцией сравнения (на 170 кусках ≈ 1250 вызовов
// сравнения по ≈ 100 тактов). Порядок тот же — по флагам, текстуре, номеру в пачке (устойчиво), — но ключом: 48 бит (флаги << 22 | (текстура + 1) << 10 | номер) и поразрядная сортировка (8 бит за проход,
// проходы, где разряд у всех одинаков, пропускаются). Нестандартные значения (флаги < 0 или ≥ 2^26, текстура < −1 или > 4094, пачка > 1024) — вызывающий берёт прежний qsort. PROPSORT913_OLD=1 — как было.
// Чистая функция без PSP-заголовков: её же гоняет tests/propsort913/run.sh
#pragma once
#include <stdint.h>
#ifndef PROPSORT913_OLD
#define PROPSORT913_OLD 0
#endif
// ord — номера кусков в порядке рисования; 1 — готово, 0 — вход нестандартный (сортировать прежним способом)
static inline int pbSortKeys(const int *flags, const int *tex, int n, unsigned short *ord) {
  if (n <= 0 || n > 1024) return 0;
  uint64_t a[1024], b[1024]; uint64_t *src = a, *dst = b;
  for (int i = 0; i < n; i++) {
    if (flags[i] < 0 || flags[i] >= (1 << 26) || tex[i] < -1 || tex[i] > 4094) return 0;
    a[i] = ((uint64_t)(unsigned)flags[i] << 22) | ((uint64_t)(unsigned)(tex[i] + 1) << 10) | (uint64_t)(unsigned)i;
  }
  for (int shift = 10; shift < 48; shift += 8) {   // разряды выше номера; номер уже внутри ключа, устойчивость даёт порядок входа
    unsigned cnt[257] = {0}; int same = 1; unsigned first = (unsigned)((src[0] >> shift) & 255u);
    for (int i = 0; i < n; i++) { unsigned d = (unsigned)((src[i] >> shift) & 255u); cnt[d + 1]++; if (d != first) same = 0; }
    if (same) continue;
    for (int k = 0; k < 256; k++) cnt[k + 1] += cnt[k];
    for (int i = 0; i < n; i++) dst[cnt[(src[i] >> shift) & 255u]++] = src[i];
    uint64_t *t = src; src = dst; dst = t;
  }
  for (int i = 0; i < n; i++) ord[i] = (unsigned short)(src[i] & 1023u);
  return 1;
}
