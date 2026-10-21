// bench — время отдельных запросов col.c в одной точке: bench LEVEL.shr x z y h gx gz [N]
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <time.h>
#include "../../viewer/col.h"
#include "../../viewer/car.h"
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
int main(int argc, char **argv) {
  if (argc < 8) { fprintf(stderr, "bench LEVEL.shr x z y h gx gz [N]\n"); return 2; }
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 1; fclose(f);
  uint32_t pvs = *(uint32_t *)(b + 88), col = *(uint32_t *)(b + 92);
  ColWorld W; if (colInit(&W, b + col, (unsigned)((pvs > col ? pvs : (uint32_t)n) - col))) return 1;
  Car c; carInit(&c, 0, &W, atof(argv[2]), atof(argv[4]), atof(argv[3]), atof(argv[5]));
  c.x = atof(argv[2]); c.z = atof(argv[3]); c.y = atof(argv[4]); c.h = atof(argv[5]); c.gx = atof(argv[6]); c.gz = atof(argv[7]);
  int N = argc > 8 ? atoi(argv[8]) : 20000;
  CarBox bx; float mx, mz, nx, nz, g; double t0, best;
  #define T(name, expr) best = 1e9; for (int r = 0; r < 5; r++) { t0 = now(); for (int i = 0; i < N; i++) { expr; } double e = (now() - t0) / N; if (e < best) best = e; } printf("%-28s %7.3f us\n", name, best * 1e6);
  T("colPushCar", carBox(&c, &bx); colPushCar(&W, &bx, &mx, &mz, &nx, &nz))
  T("colProbeCar", carBox(&c, &bx); colProbeCar(&W, &bx))
  T("colGround (origin)", colGround(&W, c.x, c.z, c.y + 0.5f, -1e6f, &g, 0))
  T("colCrossFence (0.25 m)", colCrossFence(&W, c.x, c.z, c.x + 0.2f, c.z + 0.15f, 0, 0))
  CarInput in = {1, 0, 0.3f, 0};
  T("carUpdate (1/60 s, gas)", Car cc = c; carUpdate(&cc, &W, &in, 1.f / 60))
  CarInput idle = {0, 0, 0, 0};
  T("carUpdate (1/60 s, idle)", Car cc = c; carUpdate(&cc, &W, &idle, 1.f / 60))
  carBox(&c, &bx); colProbeCar(&W, &bx); printf("shapes in narrow phase: %d\n", bx.nshapes);
#ifdef COL_DEBUG
  { extern long colStat[4]; memset(colStat, 0, sizeof colStat); Car cc = c; carUpdate(&cc, &W, &in, 1.f / 60);
    printf("one carUpdate(1/60): gathers %ld, colGround %ld, colCrossFence %ld, push iterations %ld; after: pen %.4f y %.4f grounded %d wheels %d reverts %d why %d\n", colStat[0], colStat[1], colStat[2], colStat[3], cc.pen, cc.y, cc.grounded, cc.wheels, cc.reverts, cc.revWhy); }
#endif
  return 0;
}
