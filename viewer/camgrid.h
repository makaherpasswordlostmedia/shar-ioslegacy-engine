// №620 дешёвая версия (CAM_GEOM_FAST, по умолчанию 1): грубая сетка занятости клетки по ВИДИМЫМ треугольникам города (воксель CG_VX м). Строится один раз
// при загрузке клетки (loadCell), в кадре — только шаги луча опора -> глаз по сетке (~0,1 мс), без выборки вершин. Горизонтальные грани (земля, плоские
// крыши, |ny| > CG_NY) не метятся: земля и крыши — дело коллизии, иначе луч вдоль дороги цеплял бы воксель земли. CAM_GEOM_FAST=0 — прежний путь по
// треугольникам (раз за кадр собираются в сцену). Файл зависит от Piece/Cell (main_state.h).
#ifndef SHAR_CAMGRID_H
#define SHAR_CAMGRID_H
#include <math.h>
#include <stdlib.h>
#include <string.h>
#ifndef CAM_GEOM_FAST
#define CAM_GEOM_FAST 1
#endif
#define CG_VX .75f
#ifndef CG_PROF
#define CG_PROF 0   // 1 — считать мкс в cgStep/cgRayFrac (строка CAMIN gusray/gusstep); сам таймер дорог
#endif
#define CG_TIME() (CG_PROF ? sceKernelGetSystemTimeLow() : 0u)
#ifndef CG_SCAN_OLD
#define CG_SCAN_OLD 0
#endif
#define CG_NY .8f
#define CG_MAXN 110
static inline int cgIdx(const Cell *c, int ix, int iy, int iz) { return (iz * c->cgn[1] + iy) * c->cgn[0] + ix; }
static inline void cgMark(Cell *c, const float p[3]) {
  int ix = (int)((p[0] - c->bb[0]) / CG_VX), iy = (int)((p[1] - c->bb[1]) / CG_VX), iz = (int)((p[2] - c->bb[2]) / CG_VX);
  if (ix < 0 || iy < 0 || iz < 0 || ix >= c->cgn[0] || iy >= c->cgn[1] || iz >= c->cgn[2]) return;
  int i = cgIdx(c, ix, iy, iz); ((unsigned char *)c->cg)[i >> 3] |= (unsigned char)(1u << (i & 7));
}
static unsigned cgWork;   // метки, поставленные за кадр (бюджет работы построения)
static void cgTri(Cell *c, const float a[3], const float b[3], const float d[3], int depth) {
  float ab[3] = {b[0] - a[0], b[1] - a[1], b[2] - a[2]}, bd[3] = {d[0] - b[0], d[1] - b[1], d[2] - b[2]}, da[3] = {a[0] - d[0], a[1] - d[1], a[2] - d[2]};
  float l0 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2], l1 = bd[0] * bd[0] + bd[1] * bd[1] + bd[2] * bd[2], l2 = da[0] * da[0] + da[1] * da[1] + da[2] * da[2];
  float lm = l0 > l1 ? (l0 > l2 ? l0 : l2) : (l1 > l2 ? l1 : l2);
  if (lm <= CG_VX * CG_VX * .6f || depth >= 6) { cgWork++; float m[3] = {(a[0] + b[0] + d[0]) / 3, (a[1] + b[1] + d[1]) / 3, (a[2] + b[2] + d[2]) / 3}; cgMark(c, a); cgMark(c, b); cgMark(c, d); cgMark(c, m); return; }
  float mid[3];
  if (lm == l0) { for (int k = 0; k < 3; k++) mid[k] = (a[k] + b[k]) * .5f; cgTri(c, a, mid, d, depth + 1); cgTri(c, mid, b, d, depth + 1); }
  else if (lm == l1) { for (int k = 0; k < 3; k++) mid[k] = (b[k] + d[k]) * .5f; cgTri(c, a, b, mid, depth + 1); cgTri(c, a, mid, d, depth + 1); }
  else { for (int k = 0; k < 3; k++) mid[k] = (d[k] + a[k]) * .5f; cgTri(c, a, b, mid, depth + 1); cgTri(c, mid, b, d, depth + 1); }
}
// Порционно (№620: после телепорта грузится много клеток разом — строить всё сразу нельзя): cgStep зовётся раз в кадр из главного потока, строит сетку
// одной ближней клетки не больше CG_BUDGET треугольников за кадр; пока сетка не готова (cgs != 2), клетка в луче не участвует
#define CG_US 100u   // мкс на кадр: время, не число треугольников (глубина разбиения у больших стен разная)
static unsigned cgDone, cgVox, cgDbg, cgFrame, cgReuse, cgUsStep, cgUsRay, cgStepN;
static float cgS[16]; static unsigned cgTotTri, cgSkipNy;
static void cgStep2(float ex, float ez);
// TEST24 (цена, ph6): стройка сетки съедала ~320 мкс на кадр при бюджете 100 (время сверялось через треугольник, крупные — до 96 меток). Теперь бюджет CG_US2 мкс, проверка каждый треугольник, до 32 меток.
// CG_BUDGET_OLD=1 / flag cgbudgetold 1 — как было
#ifndef CG_US2
#define CG_US2 40
#endif
#ifndef CG_BUDGET_OLD
#define CG_BUDGET_OLD 0
#endif
static int cgBudgetOld = CG_BUDGET_OLD;
static unsigned cgPf[4]; static float cgAhX = -1e9f, cgAhZ;
static int cgProf; static unsigned cgGen = 1;   // cgProf — таймеры камеры только под smoke flag camin; cgGen — поколение клеток (выгрузка/смена уровня сбрасывает кэш клеток луча)
static unsigned cgBuildN, cgBuildUs, cgScanN, cgScanUs;   // служебное (CAMIN gb/gs): кадры со стройкой сетки (> 150 мкс) и обычные
static void cgStep(float ex, float ez) { unsigned t0 = cgProf ? sceKernelGetSystemTimeLow() : 0; cgFrame++; cgStep2(ex, ez); if (!cgProf) { cgStepN++; return; } unsigned d_ = sceKernelGetSystemTimeLow() - t0; if (CG_PROF) cgUsStep += d_; cgStepN++; if (d_ > 150) { cgBuildN++; cgBuildUs += d_; } else { cgScanN++; cgScanUs += d_; } }
static void cgStep2(float ex, float ez) {
  if (!CAM_GEOM_FAST || !cl) return;
  // Аудит FPS: перебор всех клеток (1100+) каждый кадр ради «есть ли недостроенная» — впустую, когда всё построено. Нашли пусто — следующий перебор через 8 кадров
  // (клетка догружается — сетка начнёт строиться не позже чем через 8 кадров). CG_SCAN_OLD=1 — перебор каждый кадр
  static int cgIdle; if (!CG_SCAN_OLD && cgIdle && (cgFrame & 7u)) return;
  unsigned tA_ = cgProf ? sceKernelGetSystemTimeLow() : 0; Cell *c = 0; float bd = 1e30f;
  for (unsigned i = 0; i < ncell; i++) { Cell *q = &cl[i]; if (q->state != 2 || q->cgs == 2) continue;
    float dx = q->cx - ex, dz = q->cz - ez, d = dx * dx + dz * dz;
    if (cgAhX > -1e8f) { float ax = q->cx - cgAhX, az = q->cz - cgAhZ, da = ax * ax + az * az + 900.f; if (da < d) d = da; }   // клетки по ходу глаза — тоже в очередь (поправка 30 м: клетка под глазом строится первой)
    if (d < bd) { bd = d; c = q; } }
  if (cgProf) cgPf[0] += sceKernelGetSystemTimeLow() - tA_;
  if (!c) { cgIdle = 1; return; }
  cgIdle = 0; unsigned tB_ = cgProf ? sceKernelGetSystemTimeLow() : 0;
  if (c->cgs == 0) {
    int nx = (int)ceilf((c->bb[3] - c->bb[0]) / CG_VX) + 1, ny = (int)ceilf((c->bb[4] - c->bb[1]) / CG_VX) + 1, nz = (int)ceilf((c->bb[5] - c->bb[2]) / CG_VX) + 1;
    if (nx > CG_MAXN || ny > CG_MAXN || nz > CG_MAXN || nx < 1 || ny < 1 || nz < 1) { c->cgs = 2; c->cg = 0; return; }
    size_t bytes = ((size_t)nx * ny * nz + 7) >> 3; unsigned char *g = calloc(bytes, 1); if (!g) { c->cgs = 2; return; }
    c->cgn[0] = (unsigned char)nx; c->cgn[1] = (unsigned char)ny; c->cgn[2] = (unsigned char)nz; c->cgbytes = (unsigned)bytes; c->cgk = c->first; c->cgi = 0; c->cg = g; c->cgs = 1;
  }
  if (cgProf) cgPf[1] += sceKernelGetSystemTimeLow() - tB_;
  cgWork = 0; int budget = 1 << 30, tick = 0; unsigned t0 = sceKernelGetSystemTimeLow();
  while (c->cgk < c->first + c->n && budget > 0) {
    const Piece *d = &pc[c->cgk]; const Rec *r = &d->r;
    if (r->owner != 0 || (r->flags & 4) || !d->v || r->ni < 3 || r->sc <= 0.f || (!(r->flags & F_NOIDX) && !d->idx)) { c->cgk++; c->cgi = 0; continue; }
    int v12 = (r->flags & F_V12) != 0, vs = v12 ? 12 : 16, xo = v12 ? 6 : 8, noidx = (r->flags & F_NOIDX) != 0, n = r->ni - r->ni % 3;
    const char *vbase = (const char *)d->v;
    if (r->flags & F_STRIP) { unsigned nl_; vbase = (const char *)pieceListT(d, 0, &nl_); if (!vbase) { c->cgk++; c->cgi = 0; continue; } n = (int)(nl_ - nl_ % 3); }   // К4: полосы -> список (слот 0)
    while (c->cgi < n && budget > 0) {
      int i = c->cgi; c->cgi += 3;
      if (cgWork > (cgBudgetOld ? 96 : 32) || ((++tick & (cgBudgetOld ? 1 : 0)) == 0 && sceKernelGetSystemTimeLow() - t0 > (cgBudgetOld ? CG_US : CG_US2))) budget = 0;   // крупный треугольник = много вокселей: ещё и по числу меток
      float w[3][3];
      for (int j = 0; j < 3; j++) {
        unsigned vi = noidx ? (unsigned)(i + j) : d->idx[i + j];
        const short *xy = (const short *)(vbase + vi * vs + xo);
        w[j][0] = r->ox + (r->sc * (1.f / 32768.f)) * xy[0]; w[j][1] = r->oy + (r->sc * (1.f / 32768.f)) * xy[1]; w[j][2] = r->oz + (r->sc * (1.f / 32768.f)) * xy[2];
      }
      float e1[3] = {w[1][0] - w[0][0], w[1][1] - w[0][1], w[1][2] - w[0][2]}, e2[3] = {w[2][0] - w[0][0], w[2][1] - w[0][1], w[2][2] - w[0][2]};
      float nxv = e1[1] * e2[2] - e1[2] * e2[1], nyv = e1[2] * e2[0] - e1[0] * e2[2], nzv = e1[0] * e2[1] - e1[1] * e2[0], nl = sqrtf(nxv * nxv + nyv * nyv + nzv * nzv);
      cgTotTri++; if (cgDbg < 3 && i == 0) { cgDbg++; memcpy(cgS, w[0], 12); memcpy(cgS + 3, c->bb, 24); cgS[9] = r->ox; cgS[10] = r->sc; cgS[11] = (float)c->n; }
      if (nl < 1e-6f || fabsf(nyv) / nl > CG_NY) { cgSkipNy++; continue; }
      cgTri(c, w[0], w[1], w[2], 0);
    }
    if (c->cgi >= n) { c->cgk++; c->cgi = 0; }
  }
  if (c->cgk >= c->first + c->n) { c->cgs = 2; cgDone++; cgVox += c->cgbytes; }   // gvox = байт сеток (без подсчёта занятых: перебор 100+ КБ стоил мс)
}
static inline int cgOcc(const Cell *c, const float p[3]) {
  int ix = (int)((p[0] - c->bb[0]) / CG_VX), iy = (int)((p[1] - c->bb[1]) / CG_VX), iz = (int)((p[2] - c->bb[2]) / CG_VX);
  if (ix < 0 || iy < 0 || iz < 0 || ix >= c->cgn[0] || iy >= c->cgn[1] || iz >= c->cgn[2]) return 0;
  int i = cgIdx(c, ix, iy, iz); return (((const unsigned char *)c->cg)[i >> 3] >> (i & 7)) & 1;
}
// доля пути a -> b до первого занятого вокселя (шаг 0,5 м; первые CG_SKIP м от опоры не в счёт: над крышей машины, под навесом)
#define CG_SKIP .8f
static unsigned cgCalls, cgHits, cgCellsOcc;
// Кэш (№620, «проверять при сдвиге глаза > 0,2 м или раз в 2 кадра»): тот же луч (оба конца сдвинулись меньше CG_REUSE м) в следующем кадре берёт прошлый
// ответ, не позже чем через кадр пересчитывается. CAM_GEOM_CACHE_OLD=1 — каждый кадр
#define CG_REUSE .2f
#ifndef CAM_GEOM_CACHE_OLD
#define CAM_GEOM_CACHE_OLD 0
#endif
static int cgCacheOld = CAM_GEOM_CACHE_OLD;
#if 0
#endif

static struct { float a[3], b[3], r; unsigned fr; } cgCache[8]; static int cgCacheN;
static float cgRayFrac2(const float a[3], const float b[3], float skip);
static float cgRayFrac(const float a[3], const float b[3], float skip) {
  unsigned t0 = CG_TIME(); float rr;
  if (cgCacheOld) { rr = cgRayFrac2(a, b, skip); if (CG_PROF) cgUsRay += sceKernelGetSystemTimeLow() - t0; return rr; }
  for (int i = 0; i < 8; i++) { if (cgCache[i].fr == 0 || cgFrame - cgCache[i].fr != 1) continue;
    float da = 0.f, db = 0.f; for (int k = 0; k < 3; k++) { float x = a[k] - cgCache[i].a[k], y = b[k] - cgCache[i].b[k]; da += x * x; db += y * y; }
    if (da < CG_REUSE * CG_REUSE && db < CG_REUSE * CG_REUSE) { cgReuse++; if (CG_PROF) cgUsRay += sceKernelGetSystemTimeLow() - t0; return cgCache[i].r; } }
  float r = cgRayFrac2(a, b, skip);
  int j = cgCacheN++ & 7; memcpy(cgCache[j].a, a, 12); memcpy(cgCache[j].b, b, 12); cgCache[j].r = r; cgCache[j].fr = cgFrame;
  if (CG_PROF) cgUsRay += sceKernelGetSystemTimeLow() - t0;
  return r;
}
static float cgRayFrac2(const float a[3], const float b[3], float skip) {
  float d[3] = {b[0] - a[0], b[1] - a[1], b[2] - a[2]}, L = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
  if (L < 1e-3f) return 1.f;
  float lo[3], hi[3]; for (int k = 0; k < 3; k++) { lo[k] = fminf(a[k], b[k]); hi[k] = fmaxf(a[k], b[k]); }
  // список клеток у луча — из кэша, пока луч внутри коробки кэша (± CG_CL_PAD м) и не прошло 8 кадров: перебор всех клеток на каждый из ~15 лучей кадра стоил больше самого шага
  static const Cell *cc[8]; static int ccN; static float ccLo[3], ccHi[3]; static unsigned ccFr = 1u << 31, ccNcell, ccGen;
  const Cell **near = cc; int nn;
  if (cgFrame - ccFr < 8u && ccNcell == ncell && ccGen == cgGen && lo[0] >= ccLo[0] && lo[1] >= ccLo[1] && lo[2] >= ccLo[2] && hi[0] <= ccHi[0] && hi[1] <= ccHi[1] && hi[2] <= ccHi[2]) nn = ccN;
  else {
    nn = 0; for (int k = 0; k < 3; k++) { ccLo[k] = lo[k] - 4.f; ccHi[k] = hi[k] + 4.f; }
    for (unsigned i = 0; i < ncell && nn < 8; i++) { const Cell *c = &cl[i];
      if (c->state == 2 && c->cg && c->cgs == 2 && c->bb[0] <= ccHi[0] && c->bb[3] >= ccLo[0] && c->bb[1] <= ccHi[1] && c->bb[4] >= ccLo[1] && c->bb[2] <= ccHi[2] && c->bb[5] >= ccLo[2]) cc[nn++] = c; }
    ccN = nn; ccFr = cgFrame; ccNcell = ncell; ccGen = cgGen; }
  cgCalls++;
  if (!nn) return 1.f;
  for (float t = skip; t < L; t += .35f) {
    float p[3] = {a[0] + d[0] * (t / L), a[1] + d[1] * (t / L), a[2] + d[2] * (t / L)};
    for (int i = 0; i < nn; i++) if (near[i]->cg && cgOcc(near[i], p)) { cgHits++; return t / L; }
  }
  return 1.f;
}
#endif
