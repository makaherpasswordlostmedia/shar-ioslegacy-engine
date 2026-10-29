#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "car.h"
static ColWorld W;
static void step(Car *c, float thr, float brk, float st) { CarInput in = {thr, brk, st, 0}; carUpdate(c, &W, &in, 1.f / 60.f); }
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); unsigned n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != n) return 2; fclose(f);
  unsigned co = *(unsigned *)(b + 92), po = *(unsigned *)(b + 96), pv = *(unsigned *)(b + 88), end = n; if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  colInit(&W, b + co, end - co); Car c0; FILE *g = fopen(argv[2], "rb"); if (fread(&c0, sizeof c0, 1, g) != 1) return 2; c0.perchT = 0; c0.perchEsc = 0; c0.glideT = 0;
  Car c = c0; float px = c.x, pz = c.z;
  for (int fr = 0; fr < 60 * 14; fr++) { step(&c, 1, 0, 0); float d = hypotf(c.x - px, c.z - pz); if ((fr >= 235 && fr < 280 && fr % 3 == 0) || fr % 90 == 0 || d > 0.4f) printf("t=%.2f (%.2f %.2f y %.2f) v %.1f glide %.2f esc %d шаг %.2f\n", fr / 60.f, c.x, c.z, c.y, c.v, c.glideT, c.perchEsc, d); px = c.x; pz = c.z; }
  return 0; }
