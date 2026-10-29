// Зонд коллизии уровня (хост, тот же col.c, что в игре): читает со stdin строки «x z [yTop yBottom]», печатает «x z высота нормаль_y найдено материал».
//   colprobe level.shr < точки > высоты
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "col.h"
static ColWorld w;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96); unsigned end = n;
  if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff);
  if (colInit(&w, cm, end - colOff)) { puts("col fail"); return 1; }
  float x, z, yt, yb; char line[256];
  while (fgets(line, sizeof line, stdin)) {
    int k = sscanf(line, "%f %f %f %f", &x, &z, &yt, &yb); if (k < 2) continue; if (k < 4) { yt = 1e4f; yb = -1e4f; }
    float g = 0, nn[3] = {0, 1, 0}; int mat = 0; int r = colGroundMat(&w, x, z, yt, yb, &g, nn, &mat);
    printf("%.2f %.2f %.3f %.3f %d %d\n", x, z, r ? g : -9999.f, nn[1], r, mat);
  }
  return 0;
}
