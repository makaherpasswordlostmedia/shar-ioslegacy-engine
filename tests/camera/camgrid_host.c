// №620: быстрая проверка геометрии у камеры (viewer/camgrid.h + camsafe.c, движковый код) на Маке.
// Сцена: фасад дома (вертикальная стена x=10), листва (вертикальный квадрат x=-6), плоская крыша и земля.
// Красный контроль: прежняя маска луча (5, без геометрии) стену не видит; новая (13, сетка) видит, на землю и крышу не срабатывает.
// cc -std=c11 -I viewer tests/camera/camgrid_host.c viewer/camsafe.c viewer/col.c -lm
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#define F_V12 1
#define F_NOIDX 2
typedef struct { int owner, flags, ni; float sc, ox, oy, oz; } Rec;
typedef struct { Rec r; const void *v; const unsigned *idx; } Piece;
typedef struct { int state; float bb[6], cx, cz; unsigned first, n; void *cg; unsigned char cgn[3], cgs; unsigned short cgk; int cgi; unsigned cgbytes; } Cell;
static Cell *cl; static unsigned ncell; static Piece *pc; static unsigned npc;
static unsigned fakeT; static unsigned sceKernelGetSystemTimeLow(void) { return fakeT += 1; }
#include "camgrid.h"
#include "camsafe.h"
static short vq[3 * 3 * 4];   // 4 треугольника, вершины v16: u,v,ABGR(4 байта),x,y,z — тут только x,y,z со смещением 8 (16 байт на вершину)
int main(void) {
  static unsigned char vb[12 * 16]; static unsigned idx[12];
  float sc = 64.f, k = 32768.f / sc;   // world = ox + sc/32768 * raw
  float V[12][3] = { {10,0,-5},{10,6,-5},{10,0,5},  {10,6,-5},{10,6,5},{10,0,5},      // стена x=10
                     {-6,0,-3},{-6,4,-3},{-6,0,3}, {-6,4,-3},{-6,4,3},{-6,0,3} };      // листва x=-6 (вертикальный квадрат)
  for (int i = 0; i < 12; i++) { short *xy = (short *)(vb + i * 16 + 8); for (int j = 0; j < 3; j++) xy[j] = (short)lroundf(V[i][j] * k); idx[i] = i; }
  Piece P = {{0, 0, 12, sc, 0, 0, 0}, vb, idx}; pc = &P; npc = 1;
  Cell C; memset(&C, 0, sizeof C); C.state = 2; C.bb[0] = -12; C.bb[1] = -1; C.bb[2] = -8; C.bb[3] = 14; C.bb[4] = 8; C.bb[5] = 8; C.cx = 0; C.cz = 0; C.first = 0; C.n = 1;
  cl = &C; ncell = 1;
  for (int i = 0; i < 200 && C.cgs != 2; i++) cgStep(0, 0);
  int bad = 0; if (C.cgs != 2) { printf("сетка не достроилась\n"); return 1; }
  static CsScene s; memset(&s, 0, sizeof s); s.geomRay = cgRayFrac;
  float P0[3] = {0, 1.5f, 0}, E1[3] = {20, 1.5f, 0}, E2[3] = {-12, 1.5f, 0}, E3[3] = {8, 1.5f, 0}, G0[3] = {0, 0.3f, 0}, G1[3] = {9, 0.3f, 0}, R0[3] = {0, 7.f, 0}, R1[3] = {9, 7.f, 0};
  float wallNew = csRayFrac(&s, P0, E1, 13), wallOld = csRayFrac(&s, P0, E1, 5), leaf = csRayFrac(&s, P0, E2, 13), shortRay = csRayFrac(&s, P0, E3, 13);
  float gnd = csRayFrac(&s, G0, G1, 13), roof = csRayFrac(&s, R0, R1, 13);
  printf("стена: прежнее %.2f, новое %.2f (ждём ~0.5); листва %.2f (ждём ~0.5); луч до стены не доходит %.2f; вдоль земли %.2f; над крышей %.2f\n", wallOld, wallNew, leaf, shortRay, gnd, roof);
  if (!(wallOld > .999f && wallNew > .4f && wallNew < .62f)) bad++;
  if (!(leaf > .4f && leaf < .62f)) bad++;
  if (shortRay < .999f || gnd < .999f || roof < .999f) bad++;
  // кэш: тот же луч со сдвигом концов 0,1 м в следующем кадре берёт прошлый ответ; со сдвигом 1 м пересчитывается
  cgStep(0, 0); float E1b[3] = {20.1f, 1.5f, 0}, E1c[3] = {20, 1.5f, 3.f}; unsigned r0 = cgReuse; csRayFrac(&s, P0, E1b, 13); csRayFrac(&s, P0, E1c, 13);
  printf("кэш: повторов %u (ждём 1)\n", cgReuse - r0); if (cgReuse - r0 != 1) bad++;
  // ближняя плоскость: глаз в 0,3 м от стены x=10 смотрит на неё. Прежнее (мир и тела) — места сколько угодно, новое (+ сетка) — почти нет
  float EY[3] = {9.7f, 1.5f, 0}, FW[3] = {1, 0, 0}, EO[3] = {5.f, 1.5f, 0};
  camNearGeomOld = 1; float nOld = csNearFree(&s, EY, FW, .6f, 1.f, 1.5f); camNearGeomOld = 0;
  float nNew = csNearFree(&s, EY, FW, .6f, 1.f, 1.5f), nOpen = csNearFree(&s, EO, FW, .6f, 1.f, 1.5f);
  printf("ближняя плоскость у стены: прежнее %.2f, новое %.2f (ждём < 0.4); на открытом месте %.2f (ждём ~1.5)\n", nOld, nNew, nOpen);
  if (!(nOld > 1.4f && nNew < .4f && nOpen > 1.4f)) bad++;
  puts(bad ? "FAIL" : "PASS"); return bad;
}
