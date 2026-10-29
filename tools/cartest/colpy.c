// Обёртка viewer/col.c для Python (ctypes): те же запросы опор, что у движка. Собирает tools/cartest/routes.py:
//   cc -O2 -shared -fPIC -I viewer tools/cartest/colpy.c viewer/col.c -o build/tmp/libcolpy.dylib
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "col.h"

static ColWorld W; static unsigned char *data;

// 0 = ок; уровень SHR7, секция COL1 до ближайшей из PVS1/PRP
int cp_load(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) return -1;
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  data = aligned_alloc(16, (n + 15) & ~15);
  if (!data || fread(data, 1, n, f) != (size_t)n) { fclose(f); return -2; }
  fclose(f);
  uint32_t pv = *(uint32_t *)(data + 88), co = *(uint32_t *)(data + 92), po = *(uint32_t *)(data + 96), end = (uint32_t)n;
  if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  return colInit(&W, data + co, end - co);
}
// самая высокая опора в [bot, top]: 1 и y, нормаль, материал (0 твёрдо, 1 куст)
int cp_ground(float x, float z, float top, float bot, float *y, float *n3, int *mat) {
  return colGroundMat(&W, x, z, top, bot, y, n3, mat);
}
void cp_grid(float *ox, float *oz, float *cell, int *w, int *h) { *ox = W.ox; *oz = W.oz; *cell = W.cell; *w = W.W; *h = W.H; }
// кузов машины по умолчанию в точке (пол y, курс h): худшее проникновение в мир (0 — чисто)
float cp_probe(float x, float y, float z, float h) {
  CarBox b = {0}; float s = __builtin_sinf(h), c = __builtin_cosf(h);
  b.x = x; b.z = z; b.fx = s; b.fz = c; b.hw = 1.10f; b.hl = 2.675f; b.y = y; b.gx = b.gz = 0; b.lo = 0.35f; b.hi = 1.6f;
  colProbeCar(&W, &b); return b.maxDepth;
}
