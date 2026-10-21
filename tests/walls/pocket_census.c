// №590 общее правило K3-3: перепись земли уровня с шагом 2 м (все слои до 3 слоёв по высоте): печатает «x z y», где точка — зона DEATH.
// Сравнение двух сборок (по умолчанию и -DPLAYABLE_ZONE_OLD=1) даёт точки, добавленные правилом кармана.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "col.h"
static ColWorld W;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = malloc((size + 15) & ~15); fread(data, 1, size, f); fclose(f);
  unsigned co = *(unsigned *)(data + 92), ce = *(unsigned *)(data + 96); if (colInit(&W, data + co, ce - co)) return 3;
  printf("npocket %u\n", W.npocket);
  for (float z = -700.f; z <= 800.f; z += 2.f) for (float x = -620.f; x <= 460.f; x += 2.f) {
    float top = 200.f, g;
    for (int k = 0; k < 3 && colGround(&W, x, z, top, -200.f, &g, 0); k++) {
      if (colDeathAtEx(&W, x, g + 0.5f, z, 0.f, 0) >= 0) printf("D %.0f %.0f %.1f\n", x, z, g);
      top = g - 1.5f;
    }
  }
  return 0;
}
