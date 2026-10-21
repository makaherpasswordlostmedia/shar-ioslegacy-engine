// Путь пешком по настоящей коллизии (бот-игрок, 03.10, разбор миссий ночи 02.10): поиск A* по сетке 0.5 м вокруг Гомера.
// Проверка клетки — тем же, чем двигается Гомер (viewer/homer.c stepMove): опора colGround не выше ступеньки над текущей
// (HOMER_STEP), спуск — до FP_DROP; тело — коробка радиусом Гомера на слое HOMER_STEP..HOMER_HEIGHT над опорой (colProbeCar);
// заборы между клетками (colCrossFence); своя машина — препятствие (кузов + радиус Гомера). Этажи: в клетке до FP_LAYERS опор
// разной высоты (крыльцо школы над тротуаром, мостки над полом). Прыжков нет: мостки m4 так не достать. Правило бота, не игры.
//   int fpPlan(cw, car, sx, sy, sz, tx, ty, tz, reach, out, cap) -> точек пути (последняя — у цели), 0 — пути нет
//   int fpClear(cw, car, ax, ay, az, bx, bz, *endY) — прямая пешком свободна (через каждые 0.25 м), 1 — да
#ifndef BOTS_FOOTPATH_H
#define BOTS_FOOTPATH_H
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "col.h"
#include "car.h"
#include "homer.h"

#define FP_CELL 0.5f
#define FP_R 40.f                 // м: полуразмер сетки (квадрат вокруг середины старт—цель)
#define FP_N 168                  // клеток по стороне (2 * FP_R / FP_CELL + запас)
#define FP_LAYERS 3
#define FP_DROP 4.f               // м: спуск за шаг (спрыгнуть с крыльца, с мостков); выше — не спускаться
#ifndef FP_BODY
#define FP_BODY (HOMER_RADIUS + .05f)
#endif
typedef struct { float x, y, z; } FpPt;

static int fpBody(const ColWorld *cw, float x, float y, float z) {   // тело Гомера помещается (1 — да)
  CarBox q; memset(&q, 0, sizeof q); q.x = x; q.z = z; q.fx = 0.f; q.fz = 1.f; q.hw = q.hl = FP_BODY; q.y = y; q.lo = HOMER_STEP; q.hi = HOMER_HEIGHT;
  colProbeCar(cw, &q); return q.maxDepth <= .05f;
}
static int fpInCar(const Car *c, float x, float y, float z) {   // точка внутри кузова своей машины (с радиусом Гомера)
  if (!c || fabsf(y - c->y) > 2.f) return 0;
  CarBox b; carBox(c, &b);
  float dx = x - b.x, dz = z - b.z, a = dx * b.fx + dz * b.fz, l = -dx * b.fz + dz * b.fx;
  return fabsf(a) < b.hl + FP_BODY && fabsf(l) < b.hw + FP_BODY;
}
// шаг из (ax, ay, az) в (bx, bz): опора под ногами (не выше ступеньки, не ниже FP_DROP), тело, забор, машина -> 1 и *by
static int fpStep(const ColWorld *cw, const Car *car, float ax, float ay, float az, float bx, float bz, float *by) {
  float g;
  if (!colGround(cw, bx, bz, ay + HOMER_STEP, ay - FP_DROP, &g, 0)) return 0;
  if (colCrossFence(cw, ax, az, bx, bz, 0, 0) || colCrossFence(cw, bx, bz, ax, az, 0, 0)) return 0;
  if (!fpBody(cw, bx, g, bz) || fpInCar(car, bx, g, bz)) return 0;
  *by = g; return 1;
}
static int fpClear(const ColWorld *cw, const Car *car, float ax, float ay, float az, float bx, float bz, float *endY) {
  float d = hypotf(bx - ax, bz - az), py = ay, px = ax, pz = az; int n = (int)(d / .25f) + 1;
  for (int k = 1; k <= n; k++) { float t = (float)k / n, x = ax + (bx - ax) * t, z = az + (bz - az) * t, g;
    if (!fpStep(cw, car, px, py, pz, x, z, &g)) return 0;
    px = x; pz = z; py = g; }
  if (endY) *endY = py;
  return 1;
}
typedef struct { float y[FP_LAYERS]; float gc[FP_LAYERS]; int par[FP_LAYERS]; unsigned char n, closed; } FpCell;
typedef struct { float k; int s; } FpHeapE;   // открытый список: пара (оценка, состояние); повтор состояния с лучшей оценкой — новой парой
static FpCell *fpGrid; static FpHeapE *fpHeap; static int fpHeapN, fpHeapCap;
static void fpPush(int s, float k) {
  if (fpHeapN >= fpHeapCap) return;
  int i = fpHeapN++;
  while (i > 0) { int p = (i - 1) / 2; if (fpHeap[p].k <= k) break; fpHeap[i] = fpHeap[p]; i = p; }
  fpHeap[i].k = k; fpHeap[i].s = s;
}
static int fpPop(void) {
  int top = fpHeap[0].s; FpHeapE e = fpHeap[--fpHeapN]; int i = 0;
  for (;;) { int c = 2 * i + 1; if (c >= fpHeapN) break; if (c + 1 < fpHeapN && fpHeap[c + 1].k < fpHeap[c].k) c++;
    if (fpHeap[c].k >= e.k) break; fpHeap[i] = fpHeap[c]; i = c; }
  if (fpHeapN) fpHeap[i] = e;
  return top;
}
// ty — высота цели (NAN — любая): дошёл, если ближе reach по плоскости и не дальше 2 м по высоте
static int fpPlan(const ColWorld *cw, const Car *car, float sx, float sy, float sz, float tx, float ty, float tz, float reach, FpPt *out, int cap) {
  if (!fpGrid) { fpGrid = malloc(sizeof(FpCell) * FP_N * FP_N); fpHeapCap = FP_N * FP_N * FP_LAYERS * 4; fpHeap = malloc(sizeof(FpHeapE) * (size_t)fpHeapCap); }
  if (hypotf(tx - sx, tz - sz) > 2.f * FP_R - 4.f) return 0;
  float ox = .5f * (sx + tx) - FP_R, oz = .5f * (sz + tz) - FP_R;   // угол сетки
  memset(fpGrid, 0, sizeof(FpCell) * FP_N * FP_N); fpHeapN = 0;
  int ci = (int)((sx - ox) / FP_CELL), cj = (int)((sz - oz) / FP_CELL);
  if (ci < 0 || cj < 0 || ci >= FP_N || cj >= FP_N) return 0;
  FpCell *c0 = &fpGrid[cj * FP_N + ci]; c0->n = 1; c0->y[0] = sy; c0->gc[0] = 0.f; c0->par[0] = -1;
  int s0 = (cj * FP_N + ci) * FP_LAYERS; fpPush(s0, hypotf(tx - sx, tz - sz));
  static const int DI[8] = {1, -1, 0, 0, 1, 1, -1, -1}, DJ[8] = {0, 0, 1, -1, 1, -1, 1, -1};
  int goal = -1, iters = 0;
  while (fpHeapN && iters < FP_N * FP_N * 2) {
    int s = fpPop(), cell = s / FP_LAYERS, L = s % FP_LAYERS, i = cell % FP_N, j = cell / FP_N; iters++;
    FpCell *C = &fpGrid[cell]; if (C->closed & (1 << L)) continue; C->closed |= (unsigned char)(1 << L);
    float x = i == ci && j == cj && L == 0 ? sx : ox + (i + .5f) * FP_CELL, z = i == ci && j == cj && L == 0 ? sz : oz + (j + .5f) * FP_CELL, y = C->y[L];
    if (hypotf(x - tx, z - tz) < reach && (isnan(ty) || fabsf(y - ty) < 2.f)) { goal = s; break; }
    for (int k = 0; k < 8; k++) {
      int ni = i + DI[k], nj = j + DJ[k]; if (ni < 0 || nj < 0 || ni >= FP_N || nj >= FP_N) continue;
      float nx = ox + (ni + .5f) * FP_CELL, nz = oz + (nj + .5f) * FP_CELL, ny, my;
      if (!fpStep(cw, car, x, y, z, .5f * (x + nx), .5f * (z + nz), &my) || !fpStep(cw, car, .5f * (x + nx), my, .5f * (z + nz), nx, nz, &ny)) continue;
      FpCell *N = &fpGrid[nj * FP_N + ni]; int nl = -1;
      for (int q = 0; q < N->n; q++) if (fabsf(N->y[q] - ny) < .5f) { nl = q; break; }
      if (nl < 0) { if (N->n >= FP_LAYERS) continue; nl = N->n++; N->y[nl] = ny; N->gc[nl] = 1e30f; }
      if (N->closed & (1 << nl)) continue;
      float g = C->gc[L] + (k < 4 ? 1.f : 1.41421356f) * FP_CELL + fmaxf(0.f, ny - y) * .5f;   // подъём чуть дороже
      if (g < N->gc[nl]) { N->gc[nl] = g; N->par[nl] = s; fpPush((nj * FP_N + ni) * FP_LAYERS + nl, g + hypotf(tx - nx, tz - nz)); }
    }
  }
  if (getenv("FP_DEBUG")) { float x0 = 1e9f, x1 = -1e9f, z0 = 1e9f, z1 = -1e9f, y0 = 1e9f, y1 = -1e9f; int nc = 0;
    for (int c = 0; c < FP_N * FP_N; c++) for (int q = 0; q < FP_LAYERS; q++) if (fpGrid[c].closed & (1 << q)) { nc++;
      float x = ox + (c % FP_N + .5f) * FP_CELL, z = oz + (c / FP_N + .5f) * FP_CELL, y = fpGrid[c].y[q];
      x0 = fminf(x0, x); x1 = fmaxf(x1, x); z0 = fminf(z0, z); z1 = fmaxf(z1, z); y0 = fminf(y0, y); y1 = fmaxf(y1, y); }
    fprintf(stderr, "fp: раскрыто %d (итер %d), x %.1f..%.1f z %.1f..%.1f y %.2f..%.2f, цель %s\n", nc, iters, x0, x1, z0, z1, y0, y1, goal >= 0 ? "да" : "нет"); }
  if (goal < 0) return 0;
  int n = 0; for (int s = goal; s >= 0 && s != s0; s = fpGrid[s / FP_LAYERS].par[s % FP_LAYERS]) n++;
  if (n > cap) n = cap;
  int k = n; for (int s = goal; s >= 0 && s != s0 && k > 0; s = fpGrid[s / FP_LAYERS].par[s % FP_LAYERS]) {
    int cell = s / FP_LAYERS; k--; out[k] = (FpPt){ox + (cell % FP_N + .5f) * FP_CELL, fpGrid[cell].y[s % FP_LAYERS], oz + (cell / FP_N + .5f) * FP_CELL}; }
  return n;
}
#endif
