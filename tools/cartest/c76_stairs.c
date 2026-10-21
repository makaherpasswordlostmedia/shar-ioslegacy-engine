// №164: L1 C7-6, ступени к «гробу»: PS2 теряет 28 -> 19,9 м/с на ступенях (z 46,4 / 50,5 / 54 / 57,2) и потолок y 4,54; порт терял 28 -> 25,8 и взлетал до 5,3.
// Эталон v22_c76/jump.tsv (PS2, 50 к/с, z PS2 = -z порта). Порт едет с той же точки (z 28,17, v 27,77), газ до z 39,8, потом накат. Печатает точки сравнения: скорость ±7 % в точках после первого удара, потолок ±10 %.
// cc -std=c11 -O2 -I viewer tools/cartest/c76_stairs.c viewer/car.c viewer/col.c -lm ; ./a.out level.shr [famil_v]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "carparams.h"
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); unsigned n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != n) return 2; fclose(f);
  unsigned co = *(unsigned *)(b + 92), po = *(unsigned *)(b + 96), pv = *(unsigned *)(b + 88), end = n; if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  ColWorld w; if (colInit(&w, b + co, end - co)) return 2;
  CarParams p; carParamsFor(argc > 2 ? argv[2] : "famil_v", &p);
  float zs = 28.17f, g; if (!colGround(&w, -406.24f, -zs, 20, -20, &g, 0)) { puts("нет земли"); return 3; }
  Car c; carInit(&c, &p, &w, -406.24f, g, -zs, 3.14159265f - 0.5f * 0.0174533f);
  for (int i = 0; i < 20; i++) carUpdate(&c, &w, &(CarInput){0}, 1.f / 50);
  carSetSpeed(&c, 27.77f);
  struct { float z, v, y; } ref[] = {{46.4f, 27.97f, -0.07f}, {50.5f, 22.51f, 0.40f}, {54.0f, 20.07f, 1.76f}, {57.2f, 19.90f, 3.18f}, {60.3f, 19.27f, 4.05f}, {63.5f, 19.07f, 4.54f}};
  float ymax = -1e9, vgot[6], ygot[6]; int k = 0; float y0 = g;
  for (int fr = 0; fr < 50 * 6 && k < 6; fr++) {
    CarInput in = {0}; in.throttle = (-c.z) < 39.8f ? 1.f : 0.f; carUpdate(&c, &w, &in, 1.f / 50);
    float zp = -c.z, v = hypotf(c.vel[0], c.vel[2]); if (c.y - y0 > ymax) ymax = c.y - y0;
    if (getenv("TRACE") && fr % 2 == 0 && zp > 44.f && zp < 70.f) printf("  z=%.2f y=%.2f v=%.2f wheels=%d x=%.2f\n", zp, c.y - y0, v, c.wheels, c.x);
    while (k < 6 && zp >= ref[k].z) { vgot[k] = v; ygot[k] = c.y - y0; k++; }
  }
  int bad = 0;
  printf("точка z\tPS2 v\tпорт v\tPS2 y\tпорт y\n");
  for (int i = 0; i < k; i++) { printf("%.1f\t%.2f\t%.2f\t%.2f\t%.2f\n", ref[i].z, ref[i].v, vgot[i], ref[i].y, ygot[i]); if (i >= 1 && fabsf(vgot[i] - ref[i].v) > 0.07f * ref[i].v) bad++; }
  printf("потолок y: порт %.2f (PS2 4,54 ±10 %% и не выше 5,0)\n", ymax); if (ymax > 4.54f * 1.1f || ymax < 4.54f * 0.9f) bad++;
  printf("RESULT %s\n", bad ? "FAIL" : "PASS"); return bad ? 1 : 0;
}
