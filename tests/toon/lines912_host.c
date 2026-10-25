// №912: линии мультика — отбор записей и подача в GE по настоящим файлам TLN2 (toonlines.shr, roadlines.shr) уровней. Мак, только файлы.
// Идёт по случайной ходьбе глаза (шаг 0,15 м), на каждом кадре печатает: F номер линий_нарисовано хеш_набора_линий подач матриц. Набор линий — множество номеров линий, попавших в DrawArray (порядок и разбиение
// на подачи не важны), хеш — по нему. Два бинарника (прежний -DTLBATCH912_OLD=1 и новый) сверяет tests/toon/lines912.sh.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
typedef struct { float x, y, z, w; } ScePspFVector4;
typedef struct { ScePspFVector4 x, y, z, w; } ScePspFMatrix4;
#define GU_LINES 1
#define GU_VERTEX_16BIT 2
#define GU_TRANSFORM_3D 4
#define GU_MODEL 0
typedef struct { int16_t cx, cz; uint32_t first, count; } TlCell;
#define TL_CELL 64.f
#define TL_RANGE 60.f
static int mats, draws; static const int16_t *gV; static unsigned char *bits; static unsigned nlinesDrawn;
static void sceGuSetMatrix(int t, const ScePspFMatrix4 *m) { (void)t; (void)m; mats++; }
static void sceGuDrawArray(int prim, int vt, int n, const void *idx, const void *v) {
  (void)prim; (void)vt; (void)idx; draws++; size_t first = (size_t)((const int16_t *)v - gV) / 6;
  for (int i = 0; i < n / 2; i++) { if (!bits[first + (size_t)i]) nlinesDrawn++; bits[first + (size_t)i] = 1; }
}
static int tlSelReset;
#include "../../viewer/tlines.h"
static int readSet(const char *fn, TlCell **pc, int16_t **pv, unsigned *pnc, unsigned *pn) {
  FILE *f = fopen(fn, "rb"); if (!f) return 0; uint32_t h[3]; if (fread(h, 4, 3, f) != 3 || h[0] != 0x324E4C54u) { fclose(f); return 0; }
  TlCell *c = malloc((size_t)h[1] * sizeof(TlCell)); int16_t *v = malloc((size_t)h[2] * 12 + 16);
  int ok = fread(c, sizeof(TlCell), h[1], f) == h[1] && fread(v, 12, h[2], f) == h[2]; fclose(f); if (!ok) return 0; *pc = c; *pv = v; *pnc = h[1]; *pn = h[2]; return 1;
}
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: %s toonlines.shr roadlines.shr seed [frames]\n", argv[0]); return 2; }
  TlCell *tC = 0, *rC = 0; int16_t *tV = 0, *rV = 0, *tY = 0, *rY = 0; unsigned tNC = 0, tN = 0, rNC = 0, rN = 0;
  readSet(argv[1], &tC, &tV, &tNC, &tN); readSet(argv[2], &rC, &rV, &rNC, &rN);
  tlBandSplit(&tC, tV, &tNC, &tY); tlBandSplit(&rC, rV, &rNC, &rY);
  srand((unsigned)atoi(argv[3])); int frames = argc > 4 ? atoi(argv[4]) : 1500;
  unsigned maxN = (tN > rN ? tN : rN) + 8; bits = calloc(maxN, 1);
  // старт: центр случайной клетки с линиями; высота глаза — высота её первой линии + 1,7 м
  const TlCell *s0 = tNC ? &tC[rand() % tNC] : &rC[rand() % rNC]; float ex = (s0->cx + .5f) * TL_CELL, ez = (s0->cz + .5f) * TL_CELL, ey = 0.f; { const int16_t *L = (tNC ? tV : rV) + (size_t)s0->first * 6; ey = L[1] * .01f + 1.7f; }
  float yaw = (rand() & 1023) * (6.2831853f / 1024.f);
  for (int fr = 0; fr < frames; fr++) {
    if (!(fr % 40)) yaw += ((rand() & 255) - 128) * .01f;
    ex += cosf(yaw) * .15f; ez += sinf(yaw) * .15f;
    memset(bits, 0, maxN); mats = draws = 0; nlinesDrawn = 0;
    gV = tV; if (tNC) tlDrawSet(tC, tV, tY, tNC, 0, ex, ey, ez, 0.f);
    unsigned a = nlinesDrawn; unsigned h = 2166136261u; for (unsigned i = 0; i < tN; i++) if (bits[i]) h = (h ^ (i + 1)) * 16777619u;
    memset(bits, 0, maxN); nlinesDrawn = 0; gV = rV; if (rNC) tlDrawSet(rC, rV, rY, rNC, 0, ex, ey, ez, -.085f);
    unsigned b = nlinesDrawn; for (unsigned i = 0; i < rN; i++) if (bits[i]) h = (h ^ (i + 100000u)) * 16777619u;
    memset(bits, 0, maxN); nlinesDrawn = 0; gV = tV; if (tNC) tlDrawSet(tC, tV, tY, tNC, 1, ex, ey, ez, 0.f);   // толстая линия: второй проход
    printf("F %d %u %u %08x %d %d\n", fr, a, b, h, mats, draws);
  }
  return 0;
}
