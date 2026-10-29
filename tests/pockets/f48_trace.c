#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "car.h"
static ColWorld W;
static void step(Car *c, float thr, float brk, float st) { CarInput in = {thr, brk, st, 0}; carUpdate(c, &W, &in, 1.f / 60.f); }
static float side(const ColSeg *G, float x, float z) { return (x - G->a[0]) * G->n[0] + (z - G->a[1]) * G->n[1]; }
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *d = malloc((size + 15) & ~15); fread(d, 1, size, f); fclose(f);
  unsigned co = *(unsigned *)(d + 92), ce = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88); if (pv > co && pv < ce) ce = pv; colInit(&W, d + co, ce - co);
  int seg = -1; float bd = 1e9f; for (unsigned i = 0; i < W.nseg; i++) { const ColSeg *G = &W.seg[i]; if (G->y1 > 1e5f) continue; float mx = (G->a[0] + G->b[0]) * .5f, mz = (G->a[1] + G->b[1]) * .5f, dd = hypotf(mx + 162.86f, mz + 310.23f); if (dd < bd) { bd = dd; seg = (int)i; } }
  const ColSeg *G = &W.seg[seg]; printf("seg %d top %.2f n %.2f %.2f\n", seg, G->y1, G->n[0], G->n[1]);
  float st = atof(argv[2]); float g; colGround(&W, -163.f, -302.f, -3.8f, -5.3f, &g, 0); Car c; carInit(&c, NULL, &W, -163.f, g, -302.f, 3.1416f); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0);
  printf("start y %.2f ground %.2f\n", c.y, g);
  for (int fr = 0; fr < 240; fr++) { step(&c, 1, 0, st);
    if (fr % 8 == 0 || (side(G, c.x, c.z) < 0.5f && fr % 2 == 0)) printf("f%3d x %.2f y %.2f z %.2f side %.2f grounded %d wheels %d v %.1f vy %.2f\n", fr, c.x, c.y, c.z, side(G, c.x, c.z), c.grounded, c.wheels, c.v, c.vel[1]); }
  return 0; }
