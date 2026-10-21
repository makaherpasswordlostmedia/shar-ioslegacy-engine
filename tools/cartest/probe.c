// probe — отладка одного запроса colPushCar/colGround: probe LEVEL.shr x z y h [gx gz] [dx dz]
// (кузов как у машины по умолчанию; dx dz — сдвиг кузова перед запросом). Собирается с -DCOL_DEBUG.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "../../viewer/col.h"
#include "../../viewer/car.h"
extern int colDebug;
int main(int argc, char **argv) {
  if (argc < 6) { fprintf(stderr, "probe LEVEL.shr x z y h [gx gz] [dx dz]\n"); return 2; }
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 1; fclose(f);
  uint32_t pvs = *(uint32_t *)(b + 88), col = *(uint32_t *)(b + 92);
  ColWorld W; int r = colInit(&W, b + col, (unsigned)((pvs > col ? pvs : (uint32_t)n) - col)); if (r) { puts(colError(r)); return 1; }
  Car c; memset(&c, 0, sizeof c); carDefaults(&c.p);
  c.x = atof(argv[2]); c.z = atof(argv[3]); c.y = atof(argv[4]); c.h = atof(argv[5]);
  c.q[0] = cosf(c.h * .5f); c.q[2] = sinf(c.h * .5f);   // v10: кузов по кватерниону (наклон gx gz — только для печати)
  if (argc > 7) { c.gx = atof(argv[6]); c.gz = atof(argv[7]); }
  CarBox bx; carBox(&c, &bx);
  if (argc > 9) { bx.x += atof(argv[8]); bx.z += atof(argv[9]); }
  printf("box centre %.4f %.4f f %.4f %.4f hw %.2f hl %.2f floor %.3f band %.2f..%.2f\n", bx.x, bx.z, bx.fx, bx.fz, bx.hw, bx.hl, bx.y, bx.lo, bx.hi);
  colDebug = 1; float mx, mz, nx, nz;
  int k = colPushCar(&W, &bx, &mx, &mz, &nx, &nz);
  printf("contacts %d mtv %.4f %.4f n %.3f %.3f remaining %.4f behind %d shapes %d\n", k, mx, mz, nx, nz, bx.maxDepth, bx.behindFence, bx.nshapes);
  for (int i = 0; i < 4; i++) {
    float fx = sinf(c.h), fz = cosf(c.h), lon = i < 2 ? c.p.wheelF : -c.p.wheelR, lat = (i & 1) ? c.p.wheelX : -c.p.wheelX, g, nn[3];
    float x = c.x + fx * lon - fz * lat, z = c.z + fz * lon + fx * lat;
    int ok = colGround(&W, x, z, c.y + 0.35f, -1e6f, &g, nn);
    printf("wheel %d at %.2f %.2f: %s %.3f n %.2f %.2f %.2f\n", i, x, z, ok ? "ground" : "none", ok ? g : 0, ok ? nn[0] : 0, ok ? nn[1] : 0, ok ? nn[2] : 0);
  }
  return 0;
}
