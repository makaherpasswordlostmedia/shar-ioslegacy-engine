// CAMPERF (ускорение камеры, дирижёр 23.10): ответы быстрых путей камеры РАВНЫ ответам прежних, бит в бит. Мак, CPU, движковый код (viewer/col.c, camsafe.c, camgrid.h).
//   1. colRaysFrac (пакет лучей к коллизии) против colRayFrac по одному: настоящая коллизия level.shr (COL1), тысячи пирамид ближней плоскости (17 + 4 луча csNearFree) и пятёрки
//      лучей стены chaseCamUpdate, на улицах, у домов, под мостами (глаза — над случайными треугольниками коллизии);
//   2. csNearFree: camRaysOld = 0 против 1 на тех же глазах (сцена: коллизия, без сетки);
//   3. разметка сетки cgTriNew против cgTriOldF (бит в бит вся память сетки, включая грубые блоки) на случайных треугольниках всех размеров;
//   4. cgRayFrac2 с пропуском пустых блоков против прежних шагов на случайных лучах по настоящим сеткам из пункта 3.
// Сборка и запуск:  cc -std=c11 -O1 -I viewer tests/camera/camperf_host.c viewer/col.c viewer/camsafe.c -lm -o /tmp/camperf_host && /tmp/camperf_host build/level.shr
// Красный контроль:  -DCOL_RAYS_EPS=-0.5f (ящик пакета тесен — пакет теряет куски, пункты 1–2 падают);  -DCG_PLANT=1 (грубые блоки пусты — пункт 4 падает)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#define F_V12 1
#define F_NOIDX 2
#define F_STRIP 4
typedef struct { int owner, flags, ni; float sc, ox, oy, oz; } Rec;
typedef struct { Rec r; const void *v; const unsigned *idx; } Piece;
typedef struct { int state; float bb[6], cx, cz; unsigned first, n; void *cg; unsigned char cgn[3], cgs; unsigned short cgk; int cgi; unsigned cgbytes; } Cell;
static Cell *cl; static unsigned ncell; static Piece *pc; static unsigned npc;
static unsigned fakeT; static unsigned sceKernelGetSystemTimeLow(void) { return fakeT += 1; }
static const unsigned char *pieceListT(const Piece *d, int slot, unsigned *n) { (void)slot; *n = d->r.ni; return (const unsigned char *)d->v; }
#include "camgrid.h"
#include "camsafe.h"
static ColWorld world;
static unsigned rs = 12345u; static float rnd(void) { rs = rs * 1664525u + 1013904223u; return (rs >> 8) * (1.f / 16777216.f); }
static float rr(float a, float b) { return a + (b - a) * rnd(); }
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) { unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m; }
static int fails;
static void check(const char *n, long bad, long total) { printf("CHECK %-34s %s  расхождений %ld из %ld\n", n, bad ? "FAIL" : "OK  ", bad, total); fails += bad != 0; }
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) { printf("нет %s\n", lvl); return 2; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) { printf("не уровень\n"); return 2; }
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f), end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) { printf("COL1 не читается\n"); return 2; }
  // --- 1, 2: пирамиды ближней плоскости и лучи стены
  long bad1 = 0, n1 = 0, bad2 = 0, n2 = 0;
  for (int it = 0; it < 4000; it++) {
    const ColTri *T = &world.tri[(unsigned)(rnd() * world.ntri) % world.ntri];   // эйлер: глаз над случайным треугольником коллизии — город, мосты, склоны
    float eye[3] = {(T->a[0] + T->b[0] + T->c[0]) / 3 + rr(-3, 3), (T->a[1] + T->b[1] + T->c[1]) / 3 + rr(.2f, 6.f), (T->a[2] + T->b[2] + T->c[2]) / 3 + rr(-3, 3)};
    float yaw = rr(0, 6.2831853f), pit = rr(-.7f, .5f), fw[3] = {sinf(yaw) * cosf(pit), sinf(pit), cosf(yaw) * cosf(pit)};
    float r[3], u[3]; csBasis(fw, r, u); float tv = rr(.3f, .7f), th = tv * 1.7778f, D = rr(1.f, 4.f);
    float A[24][3], B[24][3], cf[24]; int m = 0;
    for (int sy = -2; sy <= 2; sy++) for (int sx = -2; sx <= 2; sx++) {
      if (sx > -2 && sx < 2 && sy > -2 && sy < 2 && (sx || sy)) continue;
      for (int k = 0; k < 3; k++) { A[m][k] = eye[k]; B[m][k] = eye[k] + D * (fw[k] + sx * .5f * th * r[k] + sy * .5f * tv * u[k]); } m++; }
    float c4[4][3]; for (int k = 0; k < 3; k++) { c4[0][k] = eye[k] + D * (fw[k] - th * r[k] - tv * u[k]); c4[1][k] = eye[k] + D * (fw[k] + th * r[k] - tv * u[k]); c4[2][k] = eye[k] + D * (fw[k] + th * r[k] + tv * u[k]); c4[3][k] = eye[k] + D * (fw[k] - th * r[k] + tv * u[k]); }
    for (int i = 0; i < 4; i++) { memcpy(A[m], c4[i], 12); memcpy(B[m], c4[(i + 1) & 3], 12); m++; }
    float T0[3] = {eye[0] + rr(-1, 1), eye[1] + rr(0, 2), eye[2] + rr(-1, 1)};   // пятёрка лучей стены: от точки взгляда к глазу и краям (7 м)
    for (int q = 0; q < 3; q++) { float d[3] = {rr(-7, 7), rr(-2, 3), rr(-7, 7)}; for (int k = 0; k < 3; k++) { A[m][k] = T0[k]; B[m][k] = T0[k] + d[k] + (q ? rr(-.4f, .4f) : 0.f); } m++; }
    colRaysFrac(&world, m, (const float (*)[3])A, (const float (*)[3])B, cf);
    for (int i = 0; i < m; i++) { float g = colRayFrac(&world, A[i], B[i], 0); n1++; if (g != cf[i]) bad1++; }
    static CsScene s; memset(&s, 0, sizeof s); s.w = &world;
    camRaysOld = 1; float o = csNearFree(&s, eye, fw, tv, th, 1.5f); camRaysOld = 0; float nw = csNearFree(&s, eye, fw, tv, th, 1.5f); n2++; if (o != nw) bad2++;
  }
  check("colRaysFrac == colRayFrac", bad1, n1);
  check("csNearFree пакет == по одному", bad2, n2);
  // --- 3, 4: сетка. Случайные треугольники всех размеров в клетке 60 × 12 × 60 м
  long bad3 = 0, n3 = 0, bad4 = 0, n4 = 0, hits4 = 0;
  for (int grid = 0; grid < 40; grid++) {
    int ntr = 30 + grid * 40; static unsigned char vb[3 * 3000 * 16]; static unsigned idx[3 * 3000]; float sc = 128.f, k = 32768.f / sc;
    for (int i = 0; i < ntr; i++) {
      float cx = rr(-28, 28), cy = rr(.5f, 11), cz = rr(-28, 28), sz = rnd() < .5f ? rr(.2f, 2.5f) : rr(2.f, 40.f);
      int vert = rnd() < .6f;   // чаще стены: горизонтальные грани сетка не метит
      for (int j = 0; j < 3; j++) { float v[3] = {cx + rr(-sz, sz) * .5f, cy + (vert ? rr(-sz, sz) * .3f : rr(-.1f, .1f)), cz + rr(-sz, sz) * (vert ? .1f : .5f)};
        short *xy = (short *)(vb + (3 * i + j) * 16 + 8); for (int q = 0; q < 3; q++) { float c = v[q] * k; xy[q] = (short)(c > 32767 ? 32767 : c < -32768 ? -32768 : lroundf(c)); } idx[3 * i + j] = 3 * i + j; }
    }
    Piece P = {{0, 0, 3 * ntr, sc, 0, 0, 0}, vb, idx}; pc = &P; npc = 1;
    static Cell C[2]; static unsigned char* mem[2];
    for (int v = 0; v < 2; v++) {
      memset(&C[v], 0, sizeof C[v]); C[v].state = 2; C[v].bb[0] = -30; C[v].bb[1] = 0; C[v].bb[2] = -30; C[v].bb[3] = 30; C[v].bb[4] = 12; C[v].bb[5] = 30; C[v].first = 0; C[v].n = 1;
      cl = &C[v]; ncell = 1; cgTriOld = v; camDet = 1;
      for (int i = 0; i < 4000 && C[v].cgs != 2; i++) cgStep(0, 0);
      mem[v] = C[v].cg;
      if (C[v].cgs != 2) { puts("сетка не достроилась"); return 1; }
    }
    unsigned total = C[0].cgbytes; n3++; if (memcmp(mem[0], mem[1], total)) bad3++;   // cgbytes: тонкая + грубая сетка
    // лучи: прежние шаги против пропуска блоков, по сетке v=0 (новая разметка = прежняя)
#ifdef CG_PLANT
    memset((unsigned char *)C[0].cg + cgFineBytes(&C[0]), 0, cgCoarseBytes(C[0].cgn));   // красный контроль: грубые блоки пусты — пропуск «не видит» занятые воксели
#endif
    cl = &C[0]; ncell = 1; cgCacheOld = 1; cgFrame = 100;
    for (int q = 0; q < 1500; q++) {
      float a[3] = {rr(-32, 32), rr(-1, 13), rr(-32, 32)}, d[3] = {rr(-9, 9), rr(-4, 4), rr(-9, 9)}, b[3] = {a[0] + d[0], a[1] + d[1], a[2] + d[2]}, skip = rnd() < .5f ? 0.f : CS_GEOM_SKIP;
      if (rnd() < .3f) { b[0] = a[0] + rr(-1.2f, 1.2f); b[1] = a[1] + rr(-1.2f, 1.2f); b[2] = a[2] + rr(-1.2f, 1.2f); }
      cgFrame++; cgCoarseOld = 1; float o = cgRayFrac(a, b, skip); cgFrame++; cgCoarseOld = 0;
      float nw = cgRayFrac(a, b, skip); n4++; if (o != nw) bad4++; if (o < 1.f) hits4++;
    }
    cgCacheOld = 0;
  }
  check("разметка сетки: память бит в бит", bad3, n3);
  check("cgRayFrac2: пропуск блоков == шаги", bad4, n4); printf("(лучей, задевших сетку: %ld из %ld — проверка не пустая)\n", hits4, n4);
  puts(fails ? "FAIL" : "PASS"); return fails;
}
