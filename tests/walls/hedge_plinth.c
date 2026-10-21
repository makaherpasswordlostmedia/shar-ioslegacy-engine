// Изгородь на каменном цоколе у домов L1 (common_gens10: ящик 820 + капсула 421, линия z ≈ 150,4, x 208,8…218,6): у PS2 твёрдая на любой скорости
// (v200_hedge: газ 4 м/с встаёт у (208,8; 150,4) со скоростью 0,17 м/с; v199_boom: 19,9 → 3,3 м/с). Заезд машиной famil_v с севера на юг (курс π,
// против +z) на 4, 10 и 15 м/с по x 210/213/216: машина обязана остановиться/откатиться, не пройти линию (z < LINE - 1,5 за 6 с — провал).
//   hedge_plinth LEVEL.shr   код 0 — держит на всех скоростях; 1 — хоть один заезд прошёл (мягкая листва); 2 — ошибка запуска
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "col.h"
#include "car.h"
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
  char *buf = malloc(sz); if (fread(buf, 1, sz, f) != (size_t)sz) return 2; fclose(f);
  ColWorld W; if (colInit(&W, buf + *(unsigned *)(buf + 92), *(unsigned *)(buf + 96) - *(unsigned *)(buf + 92))) return 2;
  CarParams P; carParamsFor("famil_v", &P); colSetFoliagePass(1);
  const float LINE = 150.4f, xs[3] = {210.f, 213.f, 216.f}, vs[3] = {4.f, 10.f, 15.f}; int passed = 0, runs = 0;
  for (int vi = 0; vi < 3; vi++) for (int xi = 0; xi < 3; xi++) {
    float sz0 = LINE + 14.f, g = 0.f; if (!colGround(&W, xs[xi], sz0, 50.f, -50.f, &g, 0)) continue;
    Car c; carInit(&c, &P, &W, xs[xi], g + .6f, sz0, 3.14159265f);
    for (int k = 0; k < 20; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
    carSetSpeed(&c, vs[vi]); float minz = c.z;
    for (int s = 0; s < 360; s++) { CarInput in = { .throttle = 1.f }; if (c.v > vs[vi]) in.throttle = 0.f; carUpdate(&c, &W, &in, 1 / 60.f); if (c.z < minz) minz = c.z; }
    int pass = minz < LINE - 1.5f; runs++; passed += pass;
    printf("  v %.0f x %.0f: ближайшая z %.2f (линия %.1f) -> %s\n", vs[vi], xs[xi], minz, LINE, pass ? "ПРОШЛА" : "держит");
  }
  printf("  изгородь на цоколе: заездов %d, прошли %d\n", runs, passed);
  return passed ? 1 : 0;
}
