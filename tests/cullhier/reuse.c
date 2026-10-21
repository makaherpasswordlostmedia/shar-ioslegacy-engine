// Хост-проверка повтора отсечения (B8, main_render.h cullCity, CULL_REUSE_OLD): список, вычисленный в позе P с запасом ящиков cullMg, обязан содержать ВСЕ куски, которые
// прежнее отсечение (без запаса) примет в любой позе P', сдвинутой не более чем на CR_EYE м и повёрнутой не более чем на CR_DIR (разность единичных векторов взгляда). Случайные пары поз L1–L7.
//   cc -O2 -std=c99 -I viewer tests/cullhier/reuse.c -lm -o build/cullreuse_host && build/cullreuse_host level.shr ...
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "cullhier.h"
#define CR_EYE .2f
#define CR_DIR .002f
typedef struct { float bb[6]; int tex, flags, nv, ni, owner; float ox, oy, oz, sc; unsigned off, nf, cell, pad[2]; } Rec;
static unsigned s_ = 99; static float rnd(void) { s_ = s_ * 1664525u + 1013904223u; return (s_ >> 8) / 16777216.f; }
static void planes(float pl[4][3], float fx, float fy, float fz) {
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl; float ux = -rz * fy, uy = rz * fx - rx * fz, uz = rx * fy;
  float tv = tanf(62.f * .5f * 3.14159265f / 180.f) * 1.03f, th = tv * (16.f / 9.f);
  float n[4][3] = {{fx * th - rx, fy * th, fz * th - rz}, {fx * th + rx, fy * th, fz * th + rz}, {fx * tv - ux, fy * tv - uy, fz * tv - uz}, {fx * tv + ux, fy * tv + uy, fz * tv + uz}};
  memcpy(pl, n, sizeof n);
}
int main(int argc, char **argv) {
  int bad = 0;
  for (int a = 1; a < argc; a++) {
    FILE *f = fopen(argv[a], "rb"); if (!f) continue; fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); unsigned char *b = malloc(sz); if (fread(b, 1, sz, f) != (size_t)sz) return 2; fclose(f);
    unsigned npc = *(unsigned *)(b + 8), ptab = *(unsigned *)(b + 76), pvsOff = *(unsigned *)(b + 88); const Rec *pc = (const Rec *)(b + ptab);
    if (!pvsOff || memcmp(b + pvsOff, "PVS1", 4)) continue;
    const float *pf = (const float *)(b + pvsOff + 4); const unsigned *pu = (const unsigned *)(b + pvsOff + 16);
    float ox = pf[0], oz = pf[1], pcell = pf[2]; unsigned W = pu[0], H = pu[1]; float range = (pu[3] >= 115 && pu[3] <= 1000) ? (float)pu[3] : 115.f;
    const unsigned *ent = (const unsigned *)(b + pvsOff + 32); const unsigned short *pool = (const unsigned short *)((const char *)ent + W * H * 8);
    unsigned *cand = malloc(W * H * 4); unsigned nc = 0; for (unsigned i = 0; i < W * H; i++) if (ent[2 * i + 1] != 0xFFFFFFFFu && ent[2 * i + 1]) cand[nc++] = i;
    long pairs = 0, missing = 0, accA = 0, accB = 0;
    for (int it = 0; it < 3000 && nc; it++) {
      unsigned e = cand[(unsigned)(rnd() * nc) % nc]; float gx = e % W, gz = e / W;
      float ex = ox + (gx + rnd()) * pcell, ez = oz + (gz + rnd()) * pcell, ey = 1.5f + rnd() * 10.f;
      float yaw = rnd() * 6.2831853f, pit = (rnd() - .35f) * 1.0f, fx = cosf(pit) * cosf(yaw), fy = sinf(pit), fz = cosf(pit) * sinf(yaw);
      float dd = rnd() < .5f ? 115.f : 250.f, pr2 = dd > range ? range * range : 1e30f, M = CR_DIR * (dd + 30.f) / 1.4f + CR_EYE + .1f;
      // сдвинутая поза P': глаз в шаре CR_EYE, вектор взгляда отклонён так, чтобы |f' - f| = CR_DIR (худший случай — граница допуска)
      float dx = rnd() - .5f, dy = rnd() - .5f, dz = rnd() - .5f, dl = sqrtf(dx * dx + dy * dy + dz * dz) + 1e-6f; float sh = CR_EYE * rnd();
      float e2x = ex + dx / dl * sh, e2y = ey + dy / dl * sh, e2z = ez + dz / dl * sh;
      float gx2 = rnd() - .5f, gy2 = rnd() - .5f, gz2 = rnd() - .5f; float tx = gx2 - (gx2 * fx + gy2 * fy + gz2 * fz) * fx, ty = gy2 - (gx2 * fx + gy2 * fy + gz2 * fz) * fy, tz = gz2 - (gx2 * fx + gy2 * fy + gz2 * fz) * fz;
      float tl = sqrtf(tx * tx + ty * ty + tz * tz) + 1e-6f; float a2 = CR_DIR * (.5f + .5f * rnd());
      float f2x = fx + tx / tl * a2, f2y = fy + ty / tl * a2, f2z = fz + tz / tl * a2, fl = sqrtf(f2x * f2x + f2y * f2y + f2z * f2z); f2x /= fl; f2y /= fl; f2z /= fl;
      if ((f2x - fx) * (f2x - fx) + (f2y - fy) * (f2y - fy) + (f2z - fz) * (f2z - fz) > CR_DIR * CR_DIR * 1.0001f) continue;
      float plA[4][3], plB[4][3]; planes(plA, fx, fy, fz); planes(plB, f2x, f2y, f2z);
      const unsigned short *lst = pool + ent[2 * e]; unsigned n = ent[2 * e + 1]; pairs++;
      for (unsigned i = 0; i < n; i++) { unsigned k = lst[i]; if (k >= npc) continue;
        float bi[6]; memcpy(bi, pc[k].bb, sizeof bi); for (int q = 0; q < 3; q++) { bi[q] -= M; bi[q + 3] += M; }
        int inA = 0; { float d2 = chBoxD2(bi, ex, ey, ez); if (d2 <= pr2 && !(d2 > dd * dd || !chVisBox(bi, plA, ex, ey, ez))) inA = 1; }
        int inB = 0; { float d2 = chBoxD2(pc[k].bb, e2x, e2y, e2z); if (d2 <= pr2 && !(d2 > dd * dd || !chVisBox(pc[k].bb, plB, e2x, e2y, e2z))) inB = 1; }
        accA += inA; accB += inB; if (inB && !inA) missing++; }
    }
    printf("%s: пар поз %ld, принято с запасом %ld, принято без запаса в сдвинутой позе %ld (лишних %.1f %%), ПРОПУЩЕНО (поп-ин) %ld\n", argv[a], pairs, accA, accB, 100.0 * (accA - accB) / (accB ? accB : 1), missing);
    if (missing) bad++;
    free(b); free(cand);
  }
  printf(bad ? "FAIL\n" : "OK\n"); return bad ? 1 : 0;
}
