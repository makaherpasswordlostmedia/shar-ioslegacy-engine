// Односторонность забора (проба Sonnet-PS2 15.10: у оригинала звено 121 L1 держит с востока — со стороны нормали, — а с запада машина проезжает на 13 м/с).
// Порт: машина стартует в 8 м от звена с заданной стороны и едет на него курсом 90° под газом; печать: пересекла ли линию, скорость и положение через 3 с.
//   fence_side_probe LEVEL.shr seg x z [speed 8]  — x z: точка на линии звена (середина участка); стороны определяются по нормали звена
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "car.h"
static ColWorld W;
int main(int argc, char **argv) {
  if (argc < 5) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *d = malloc((size + 15) & ~15); if (fread(d, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), ce = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88); if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 3;
  unsigned si = (unsigned)atoi(argv[2]); float px = atof(argv[3]), pz = atof(argv[4]), spd = argc > 5 ? atof(argv[5]) : 8.f; if (si >= W.nseg) return 4;
  const ColSeg *G = &W.seg[si]; float nx = G->n[0], nz = G->n[1];
  printf("звено %u (%.1f %.1f)-(%.1f %.1f) n(%.2f %.2f) верх %.1f\n", si, G->a[0], G->a[1], G->b[0], G->b[1], nx, nz, G->y1);
  for (int side = 1; side >= -1; side -= 2) {   // +1 — со стороны нормали («лицо»), -1 — с изнанки
    float sx = px + nx * 8.f * side, sz = pz + nz * 8.f * side, gy;
    int ok = colGround(&W, sx, sz, 200.f, -300.f, &gy, 0);
    if (!ok) { printf("  %s: старт %.1f %.1f без опоры — не проверить\n", side > 0 ? "лицо" : "изнанка", sx, sz); continue; }
    float h = atan2f(-nx * side, -nz * side);   // курс на линию
    Car c; carInit(&c, NULL, &W, sx, gy + 0.6f, sz, h); carSetSpeed(&c, spd);
    float s0 = (c.x - G->a[0]) * nx + (c.z - G->a[1]) * nz; int crossed = 0; float vmin = 1e9f;
    for (int i = 0; i < 180; i++) { CarInput in = {1.f, 0, 0, 0}; carUpdate(&c, &W, &in, 1.f / 60.f);
      float s = (c.x - G->a[0]) * nx + (c.z - G->a[1]) * nz; if (s * s0 < 0.f) crossed = 1; float v = hypotf(c.vel[0], c.vel[2]); if (i > 20 && v < vmin) vmin = v; }
    float s1 = (c.x - G->a[0]) * nx + (c.z - G->a[1]) * nz;
    printf("  %s: старт (%.1f %.1f), через 3 с: расстояние до линии %.1f м (было %.1f), %s, скорость %.1f, мин. после 0,3 с %.1f\n", side > 0 ? "лицо" : "изнанка", sx, sz, s1, s0, crossed ? "ПЕРЕСЕКЛА" : "держит", hypotf(c.vel[0], c.vel[2]), vmin);
  }
  return 0;
}
