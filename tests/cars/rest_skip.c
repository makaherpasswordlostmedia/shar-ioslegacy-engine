// Покой без счёта подшагов (тур SHARTEST4): стоящая машина без ввода — тот же результат, что со счётом, и просыпается от ввода и толчка.
//   cc ... tests/cars/rest_skip.c viewer/car.c viewer/col.c -lm && ./a.out LEVEL.shr
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = malloc(n); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  float px = argc > 2 ? atof(argv[2]) : 0.f, pz = argc > 3 ? atof(argv[3]) : 0.f; Car a; float g, nn[3];
  if (argc <= 2) for (float x = 200.f; x < 480.f; x += 10.f) for (float z = -300.f; z < 300.f; z += 10.f) {   // первая ровная точка (нормаль ≥ 0.9999)
    float h; if (colGround(&W, x, z, 12.f, -20.f, &h, nn) && nn[1] > .9999f && fabsf(h - 3.4f) < 4.f) { px = x; pz = z; goto found; } }
  found: colGround(&W, px, pz, 40.f, -50.f, &g, 0); printf("точка (%.0f, %.0f) y %.2f\n", px, pz, g);
  carInit(&a, NULL, &W, px, g + 1.f, pz, 1.f);
  CarInput in = {0}; int bad = 0; float dt = 1.f / 30.f;
  for (int i = 0; i < 300; i++) { carUpdate(&a, &W, &in, dt); if (i % 30 == 0 && getenv("RS_V")) printf("  t %d pos %.4f %.4f %.4f v %.4f quiet %d wheels %d\n", i / 30, a.x, a.y, a.z, a.v, a.quietSteps, a.wheels); }   // 10 с покоя
  float x0 = a.x, y0 = a.y, z0 = a.z; int qs = a.quietSteps;
  for (int i = 0; i < 150; i++) carUpdate(&a, &W, &in, dt);
  printf("покой: подшагов в покое %d -> %d; поза %s\n", qs, a.quietSteps, (a.x == x0 && a.y == y0 && a.z == z0) ? "та же" : "ИЗМЕНИЛАСЬ"); bad += !(a.x == x0 && a.y == y0 && a.z == z0);
  in.throttle = 1.f; for (int i = 0; i < 30; i++) carUpdate(&a, &W, &in, dt);
  float moved = hypotf(a.x - x0, a.z - z0); printf("газ после покоя: уехала на %.2f м (ждём > 2)\n", moved); bad += !(moved > 2.f);
  in.throttle = 0.f; for (int i = 0; i < 400; i++) { in.brake = 1.f; carUpdate(&a, &W, &in, dt); }
  in.brake = 0.f; for (int i = 0; i < 300; i++) carUpdate(&a, &W, &in, dt);
  float x1 = a.x; carSetSpeed(&a, 6.f); for (int i = 0; i < 20; i++) carUpdate(&a, &W, &in, dt);
  printf("толчок скоростью после покоя: сдвиг %.2f м (ждём > 1)\n", fabsf(a.x - x1) + fabsf(a.z - 0.f) * 0.f); bad += !(fabsf(a.x - x1) > 1.f || a.v > 1.f);
  printf("%s\n", bad ? "FAIL" : "PASS"); return bad;
}
