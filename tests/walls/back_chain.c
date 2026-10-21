// Забор с изнанки по ломаной (сверка PS2 09.10, docs/handoff/СТЕНЫ_СВЕРКА_PS2_2026-10-09.md; боты 09.10 L1 J12-9): машина проехала
// изгородь 1140 насквозь (решение 173) и стоит за линией; сзади по той же прямой твёрдый забор 1142, центр кузова за концом его
// звена. Задний ход 3 с на линию: прежде 1142 толкал кузов «дальше на изнанку» — машина не выезжала (боты: trapped=1).
// Зелёный: сдвиг ≥ 1 м. Красный: -DCOL_BACK_HOPS=1 или -DCOL_FENCE_BACK_OLD=1 — сдвиг < 1 м.
//   cc -std=c11 -O2 -I viewer tests/walls/back_chain.c viewer/car.c viewer/col.c -lm -o back_chain && ./back_chain build/level.shr
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "car.h"
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  static ColWorld W; if (colInit(&W, d + co, ce - co)) return 2;
  // состояние из бота (allrisk --mode hedges --only hedge:s1140:+1:70, конец 6 с): центр, курс; и два соседних места вдоль линии
  static const float P[3][3] = {{176.12f, 493.49f, 0.186f}, {176.9f, 493.3f, 0.186f}, {175.4f, 493.7f, 0.186f}};
  int bad = 0;
  for (int k = 0; k < 3; k++) {
    Car c; float g; if (!colGround(&W, P[k][0], P[k][1], 3.f, -4.f, &g, 0)) { printf("FAIL нет опоры %d\n", k); return 2; }
    carInit(&c, NULL, &W, P[k][0], g, P[k][1], P[k][2]);
    for (int i = 0; i < 30; i++) { CarInput in = {0, 0, 0, 0}; carUpdate(&c, &W, &in, 1.f / 60.f); }
    float x0 = c.x, z0 = c.z;
    for (int i = 0; i < 180; i++) { CarInput in = {0, 1, 0, 0}; carUpdate(&c, &W, &in, 1.f / 60.f); }
    float mv = hypotf(c.x - x0, c.z - z0);
    printf("%s место %d (%.1f %.1f): задний ход 3 с — %.2f м\n", mv >= 1.f ? "ok" : "FAIL", k, P[k][0], P[k][1], mv); bad += mv < 1.f;
  }
  printf("RESULT: %s\n", bad ? "FAIL" : "OK"); return bad;
}
