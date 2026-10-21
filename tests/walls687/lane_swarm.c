// трасса L2 C1-5 (x -453.8…-429.8): рой «вдоль стены» с разными боковыми смещениями/углами, руль 0; печать остановок: где и об что
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "car.h"
#include "col.h"
static ColWorld w;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); unsigned n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b,1,n,f)!=n) return 2; fclose(f);
  unsigned co = *(unsigned *)(b + 92), po = *(unsigned *)(b + 96), pv = *(unsigned *)(b + 88), end = n;
  if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  if (colInit(&w, b + co, end - co)) return 2;
  float xl = atof(argv[2]), xr = atof(argv[3]), z0 = atof(argv[4]), z1 = atof(argv[5]); int dir = atoi(argv[6]);   // dir +1: едем к +z
  CarParams p; carParamsFor("famil_v", &p); int bad = 0, runs = 0;
  for (int side = 0; side < 2; side++) for (int ia = 0; ia < 6; ia++) for (int iv = 0; iv < 3; iv++) for (int io = 0; io < 4; io++) {
    static const float AA[6] = {2, 5, 10, 15, 20, 30}; float ang = AA[ia] * 0.01745f * (side ? -1 : 1), vt = iv == 0 ? 12.f : iv == 1 ? 20.f : 28.f, off = .8f + io * .5f;
    float x = side ? xr - off - 1.2f : xl + off + 1.2f, z = dir > 0 ? z0 : z1, g; if (!colGround(&w, x, z, 80.f, -30.f, &g, 0)) continue;
    float hd = dir > 0 ? 0.f : 3.14159f; hd += ang * (side ? 1 : -1) * -1.f;   // угол к стене: нос чуть в сторону стены
    Car c; carInit(&c, &p, &w, x, g, z, hd); for (int i = 0; i < 20; i++) carUpdate(&c, &w, &(CarInput){0}, 1 / 60.f);
    carSetSpeed(&c, vt); runs++; float vsum = 0; int vn = 0, hit0 = 0; float vmn = 1e9; float tz0 = c.z; int stopped = 0; float sx = 0, sz = 0; int ct = -1; unsigned ci = 0;
    for (int fr = 0; fr < 60 * 16; fr++) { CarInput in = { .throttle = c.v < vt ? 1.f : 0.f }; carUpdate(&c, &w, &in, 1 / 60.f);
      if (c.wallV > .3f) { ct = c.wallType; ci = c.wallIdx; hit0 = 1; } if (hit0) { float vv = hypotf(c.vel[0], c.vel[2]); vsum += vv; vn++; if (vv < vmn) vmn = vv; }
      float prog = (c.z - tz0) * dir; if (fr > 90 && hypotf(c.vel[0], c.vel[2]) < 2.f && prog < (z1 - z0) * .9f && ct >= 0) { stopped = 1; sx = c.x; sz = c.z; break; }
      if (prog > (z1 - z0) * .9f) break; }
    if (hit0 && !stopped) printf("КОНТАКТ ang %+.0f v %.0f off %.1f: vmin %.1f средняя %.1f (%.0f%% от v)\n", ang * 57.3f, vt, off, vmn, vsum / vn, 100.f * vsum / vn / vt);
    if (stopped) { bad++; printf("СТОП side %d ang %+.1f° v %.0f off %.1f: x %.2f z %.2f контакт [%d:%u] y %.2f\n", side, ang * 57.3f, vt, off, sx, sz, ct, ci, c.y); } }
  printf("RESULT stops=%d runs=%d\n", bad, runs); return 0; }
