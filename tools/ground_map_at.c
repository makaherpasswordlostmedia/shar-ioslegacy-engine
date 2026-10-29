// Карта опоры вокруг точки: tools/ground_map_at.c LEVEL.shr x y z [R 8] [шаг 1] — '.' земля на высоте точки ±1,5 м, ' ' нет земли, '#' земля выше на 1,5+ (стена по высоте). Центр отмечен '@'.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "col.h"
static ColWorld W;
int main(int argc, char **argv) {
  if (argc < 5) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *d = malloc((size + 15) & ~15); if (fread(d, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), ce = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88); if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 3;
  float px = atof(argv[2]), py = atof(argv[3]), pz = atof(argv[4]), R = argc > 5 ? atof(argv[5]) : 8.f, st = argc > 6 ? atof(argv[6]) : 1.f;
  for (float z = pz + R; z >= pz - R - 1e-3f; z -= st) { printf("z%7.1f ", z);
    for (float x = px - R; x <= px + R + 1e-3f; x += st) { float g; int ok = colGround(&W, x, z, py + 1.5f, py - 1.5f, &g, 0);
      int above = !ok && colGround(&W, x, z, py + 12.f, py + 1.5f, &g, 0);
      putchar(fabsf(x - px) < st * .5f && fabsf(z - pz) < st * .5f ? '@' : ok ? '.' : above ? '#' : ' '); }
    putchar('\n'); }
  return 0;
}
