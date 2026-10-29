// Хост-модель второго прохода B2 (main_loop.h NEARPASS_OLD): пиксельный луч с фрагментами города (дальше NEAR_Z) и своей машины. Прежний путь: один проход, near 0,35, far 135, 16-бит глубина GEQUAL.
// B2: проход 1 near 1,5 (машина ближе 1,5 м обрезана), затем глубина очищена и проход 2 near 0,35 far 1,506 только фрагментов машины. Считаем, сколько раз итог не совпал с истиной (ближайший фрагмент).
//   cc -O2 -std=c99 tests/nearpass/host.c -lm -o build/nearpass_host && build/nearpass_host
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
static unsigned s_ = 31; static double rnd(void) { s_ = s_ * 1664525u + 1013904223u; return (s_ >> 8) / 16777216.0; }
static int dq(double D, double n, double f) { if (D < n || D > f) return -1; double v = 65535.0 * n * (f / D - 1.0) / (f - n); return (int)floor(v); }
int main(void) {
  const double NZ = 1.5, FAR = 135.0, N0 = .35;
  long total = 0, oldBad = 0, newBad = 0, newBadBand = 0, oldNearBad = 0, newNearBad = 0;
  for (long it = 0; it < 20000000; it++) {
    double Dc = NZ + rnd() * 60.0, Dk = N0 + rnd() * 3.0;   // город: свободное место >= NEAR_Z (csNearFree); машина: от 0,35 м
    if (rnd() < .5) Dc = NZ + rnd() * .3;                     // половина — стена в первых 30 см свободного места
    double Dc2 = Dc + (rnd() < .3 ? rnd() * .02 : rnd() * 2.0);   // второй слой города рядом по глубине (стык граней, декаль)
    int truth = 0;   // 0 — нет, 1 — город c, 2 — город c2, 3 — машина; истина: ближайший
    double best = 1e9; if (Dc < best) { best = Dc; truth = 1; } if (Dc2 < best) { best = Dc2; truth = 2; } if (Dk < best) { best = Dk; truth = 3; }
    // прежний путь: все фрагменты, 16-бит, порядок: город, машина (машина рисуется после города)
    { int zb = -1, who = 0; double D[3] = {Dc, Dc2, Dk}; int order[3] = {0, 1, 2};
      for (int k = 0; k < 3; k++) { int z = dq(D[order[k]], N0, FAR); if (z >= 0 && z >= zb) { zb = z; who = order[k] + 1; } }
      if (who != truth) { oldBad++; if (Dk < NZ) oldNearBad++; } }
    // B2
    { int zb = -1, who = 0; double D[3] = {Dc, Dc2, Dk}; int order[3] = {0, 1, 2};
      for (int k = 0; k < 3; k++) { int z = dq(D[order[k]], NZ, FAR); if (z >= 0 && z >= zb) { zb = z; who = order[k] + 1; } }
      zb = -1; { int z = dq(Dk, N0, NZ * 1.004); if (z >= 0) { zb = z; who = 3; } }   // проход 2: глубина очищена, только машина
      if (who != truth) { newBad++; if (Dk < NZ) newNearBad++; if (Dk >= NZ && Dk <= NZ * 1.004) newBadBand++; } }
    total++;
  }
  printf("лучей %ld | прежний путь неверных %ld (%.4f %%), из них машина ближе 1,5 м: %ld | B2 неверных %ld (%.4f %%), из них машина ближе 1,5 м: %ld, в полосе 1,5…1,506 м: %ld\n",
         total, oldBad, 100.0 * oldBad / total, oldNearBad, newBad, 100.0 * newBad / total, newNearBad, newBadBand);
  printf("%s\n", newBad <= oldBad ? "OK (B2 не хуже прежнего пути)" : "FAIL"); return newBad <= oldBad ? 0 : 1;
}
