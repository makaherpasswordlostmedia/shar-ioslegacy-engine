// Какие примитивы коллизии держат кузов машины в точке: colPushCar на хосте, печать типа и номера примитива (тот же col.c, что в игре).
//   colpush level.shr x z fx fz [hw hl lo hi]   — пол по colGround под центром; несколько точек со stdin: «x z fx fz»
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
static ColWorld w;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96); unsigned end = n;
  if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff); if (colInit(&w, cm, end - colOff)) return 1;
  float hw = argc > 6 ? atof(argv[6]) : 0.9f, hl = argc > 7 ? atof(argv[7]) : 2.1f, lo = argc > 8 ? atof(argv[8]) : 0.35f, hi = argc > 9 ? atof(argv[9]) : 1.6f;
  char line[256]; float x, z, fx, fz; int first = 1;
  while (1) {
    if (first && argc > 5) { x = atof(argv[2]); z = atof(argv[3]); fx = atof(argv[4]); fz = atof(argv[5]); first = 0; }
    else if (!fgets(line, sizeof line, stdin) || sscanf(line, "%f %f %f %f", &x, &z, &fx, &fz) < 4) break;
    float g = 0; if (!colGround(&w, x, z, 1e4f, -1e4f, &g, 0)) { printf("%.2f %.2f no ground\n", x, z); continue; }
    float ga = g, gb = g, gc = g, gd = g; colGround(&w, x + 1.f, z, g + 1.f, g - 1.f, &ga, 0); colGround(&w, x - 1.f, z, g + 1.f, g - 1.f, &gb, 0); colGround(&w, x, z + 1.f, g + 1.f, g - 1.f, &gc, 0); colGround(&w, x, z - 1.f, g + 1.f, g - 1.f, &gd, 0);
    CarBox b; memset(&b, 0, sizeof b); b.gx = (ga - gb) * .5f; b.gz = (gc - gd) * .5f; b.x = x; b.z = z; float l = hypotf(fx, fz); b.fx = fx / l; b.fz = fz / l; b.hw = hw; b.hl = hl; b.y = g; b.lo = lo; b.hi = hi; b.fsup = g; b.fsupOn = 1;
    float mx, mz, nx, nz; int c = colPushCar(&w, &b, &mx, &mz, &nx, &nz);
    printf("%.2f %.2f ground %.2f contacts %d maxDepth %.3f", x, z, g, c, b.maxDepth);
    for (int k = 0; k < b.n; k++) printf(" [type %d idx %u n %.2f %.2f depth %.3f]", b.type[k], b.index[k], b.nx[k], b.nz[k], b.depth[k]);
    printf("\n"); if (argc > 5) break;
  }
  return 0;
}
