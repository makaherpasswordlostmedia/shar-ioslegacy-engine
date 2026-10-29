// Хост-сверка иерархического отсечения (viewer/cullhier.h, А3): на случайных позах камеры по PVS каждого уровня множество принятых кусков прежнего цикла (дальность + 4 плоскости
// по каждому куску) и нового (класс клетки, затем куски) обязано совпасть. Плюс условие: ящик куска лежит внутри ящика его клетки.
//   cc -O2 -std=c99 -I viewer tests/cullhier/host.c -lm -o build/cullhier_host && build/cullhier_host level.shr [level2.shr ...]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "cullhier.h"
typedef struct { float bb[6]; int tex, flags, nv, ni, owner; float ox, oy, oz, sc; unsigned off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; unsigned first, n, owner, off, size, pad; } Cell;
static unsigned rnd_s = 12345; static float rnd(void) { rnd_s = rnd_s * 1664525u + 1013904223u; return (rnd_s >> 8) / 16777216.f; }
static void planes(float pl[4][3], float fx, float fy, float fz) {   // как setupPlanes (main_render.h), FOVY 62, ASPECT 16:9
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl; float ux = -rz * fy, uy = rz * fx - rx * fz, uz = rx * fy;
  float tv = tanf(62.f * .5f * 3.14159265f / 180.f) * 1.03f, th = tv * (16.f / 9.f);
  float n[4][3] = {{fx * th - rx, fy * th, fz * th - rz}, {fx * th + rx, fy * th, fz * th + rz}, {fx * tv - ux, fy * tv - uy, fz * tv - uz}, {fx * tv + ux, fy * tv + uy, fz * tv + uz}};
  memcpy(pl, n, sizeof n);
}
int main(int argc, char **argv) {
  int bad = 0;
  for (int a = 1; a < argc; a++) {
    FILE *f = fopen(argv[a], "rb"); if (!f) { printf("%s: нет файла\n", argv[a]); bad++; continue; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); unsigned char *b = malloc(sz); if (fread(b, 1, sz, f) != (size_t)sz) { printf("чтение\n"); return 2; } fclose(f);
    unsigned npc = *(unsigned *)(b + 8), ptab = *(unsigned *)(b + 76), ncell = *(unsigned *)(b + 80), ctab = *(unsigned *)(b + 84), pvsOff = *(unsigned *)(b + 88);
    const Rec *pc = (const Rec *)(b + ptab); const Cell *cl = (const Cell *)(b + ctab);
    if (!pvsOff || memcmp(b + pvsOff, "PVS1", 4)) { printf("%s: нет PVS1\n", argv[a]); continue; }
    const float *pf = (const float *)(b + pvsOff + 4); const unsigned *pu = (const unsigned *)(b + pvsOff + 16);
    float ox = pf[0], oz = pf[1], pcell = pf[2]; unsigned W = pu[0], H = pu[1]; float range = (pu[3] >= 115 && pu[3] <= 1000) ? (float)pu[3] : 115.f;
    const unsigned *ent = (const unsigned *)(b + pvsOff + 32); const unsigned short *pool = (const unsigned short *)((const char *)ent + W * H * 8);
    int outside = 0, cellsBad = 0; for (unsigned k = 0; k < npc; k++) { unsigned c = pc[k].cell; if (c >= ncell) continue; const float *bb = pc[k].bb, *cb = cl[c].bb;
      if (bb[0] < cb[0] - 1e-3f || bb[1] < cb[1] - 1e-3f || bb[2] < cb[2] - 1e-3f || bb[3] > cb[3] + 1e-3f || bb[4] > cb[4] + 1e-3f || bb[5] > cb[5] + 1e-3f) outside++; }
    unsigned *cand = malloc(W * H * 4); unsigned nc = 0; for (unsigned i = 0; i < W * H; i++) if (ent[2 * i + 1] != 0xFFFFFFFFu && ent[2 * i + 1]) cand[nc++] = i;
    long poses = 0, mism = 0, tot = 0, rejCls = 0, inside = 0, partial = 0, accepted = 0;
    for (int it = 0; it < 4000 && nc; it++) {
      unsigned e = cand[(unsigned)(rnd() * nc) % nc]; float gx = e % W, gz = e / W;
      float eyeX = ox + (gx + rnd()) * pcell, eyeZ = oz + (gz + rnd()) * pcell, eyeY = 1.5f + rnd() * 10.f;
      float yaw = rnd() * 6.2831853f, pit = (rnd() - .35f) * 1.0f, fx = cosf(pit) * cosf(yaw), fy = sinf(pit), fz = cosf(pit) * sinf(yaw);
      float dd = rnd() < .5f ? 115.f : 250.f, pr2 = dd > range ? range * range : 1e30f; float pl[4][3]; planes(pl, fx, fy, fz);
      const unsigned short *lst = pool + ent[2 * e]; unsigned n = ent[2 * e + 1]; poses++;
      for (unsigned i = 0; i < n; i++) { unsigned k = lst[i]; if (k >= npc) continue; unsigned c = pc[k].cell; if (c >= ncell) continue; tot++;
        int old = 0; { float d2 = chBoxD2(pc[k].bb, eyeX, eyeY, eyeZ); if (d2 <= pr2 && !(d2 > dd * dd || !chVisBox(pc[k].bb, pl, eyeX, eyeY, eyeZ))) old = 1; }
        int cls = chClassify(cl[c].bb, pl, eyeX, eyeY, eyeZ, dd), nw = 0;
        if (!cls) rejCls++; else { if (cls == 2) inside++; else partial++; float d2 = chBoxD2(pc[k].bb, eyeX, eyeY, eyeZ);
          if (d2 <= pr2 && !(d2 > dd * dd || (cls != 2 && !chVisBox(pc[k].bb, pl, eyeX, eyeY, eyeZ)))) nw = 1; }
        if (old != nw) mism++; accepted += nw; }
    }
    printf("%s: pieces %u cells %u PVS-cells %u | piece box outside its cell box: %d | poses %ld entries %ld: rejected by cell class %.1f%%, cell inside %.1f%%, partial %.1f%%, accepted %.1f%% | MISMATCH %ld\n",
           argv[a], npc, ncell, nc, outside, poses, tot, 100.0 * rejCls / (tot ? tot : 1), 100.0 * inside / (tot ? tot : 1), 100.0 * partial / (tot ? tot : 1), 100.0 * accepted / (tot ? tot : 1), mism);
    if (mism || outside) bad++;
    free(b); free(cand); (void)cellsBad;
  }
  printf(bad ? "FAIL\n" : "OK\n"); return bad ? 1 : 0;
}
