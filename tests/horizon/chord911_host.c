// №911: лента горизонта — самое близкое место ленты к глазу по настоящим horizon.shr всех уровней (Мак, только файлы).
// Лента рисуется на радиусе R вокруг глаза и соединяет соседние столбцы ПРЯМОЙ: хорда между столбцами с разрывом D градусов проходит от глаза на R·cos(D/2). Идёт по всем ячейкам всех уровней
// (глаз клетки — её центр: лента привязана к камере, а не к клетке). Печатает: CHORD level cells viol maxgap mind (viol — ячеек, где хорда ближе MIN_D)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "../../viewer/horizon_chord.h"
#ifndef RIBBON_R
#define RIBBON_R 154.f   // drawDist + 4 при FAR150_D = 150
#endif
#ifndef MIN_D
#define MIN_D 150.f
#endif
int main(int argc, char **argv) {
  unsigned totViol = 0, totCells = 0; float worst = 1e9f;
  for (int a = 1; a < argc; a++) {
    FILE *f = fopen(argv[a], "rb"); if (!f) { printf("FAIL: нет файла %s\n", argv[a]); return 2; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); unsigned char *b = malloc((size_t)sz); if (fread(b, 1, (size_t)sz, f) != (size_t)sz) return 2; fclose(f);
    if (memcmp(b, "HOR1", 4)) { printf("FAIL: %s не HOR1\n", argv[a]); return 2; }
    unsigned n = *(unsigned *)(b + 4), viol = 0, bad = 0; float maxgap = 0.f, mind = 1e9f;
    for (unsigned i = 0; i < n; i++) {
      const unsigned char *c = b + 32 + 32ull * i; unsigned nv = *(unsigned *)(c + 12), off = *(unsigned *)(c + 16);
      unsigned short az[HZ_CHORD_NV]; short t[HZ_CHORD_NV]; unsigned m = hzChordExpand(b + off, nv, az, t);
      if (m < nv || m > HZ_CHORD_NV) bad++;
      float cellMin = 1e9f;
      for (unsigned k = 0; k + 1 < m; k++) {
        float d = (float)((unsigned short)(az[k + 1] - az[k])) * (360.f / 65536.f); if (d > maxgap) maxgap = d;
        float dist = RIBBON_R * cosf(d * .5f * (float)M_PI / 180.f); if (dist < cellMin) cellMin = dist;
      }
      if (cellMin < mind) mind = cellMin; if (cellMin < MIN_D) viol++;
    }
    printf("CHORD %s cells=%u viol=%u maxgap=%.1f mind=%.1f bad=%u\n", argv[a], n, viol, maxgap, mind, bad);
    totViol += viol + bad; totCells += n; if (mind < worst) worst = mind; free(b);
  }
  printf("TOTAL cells=%u viol=%u mind=%.1f\n", totCells, totViol, worst);
  return totViol ? 1 : 0;
}
