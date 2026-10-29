// mcrprof — нагрузочная петля для профилировщика (sample): записанный ввод миссии проигрывается REPS раз подряд, мир каждый раз
// возвращается снимком в начало миссии. Печатает мкс на кадр и на машину ИИ миссии (Mac), отпечаток последнего прогона.
//   mcrprof LEVEL HOMER MSN INPUT MISSION REPS
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "world.h"
#include "col.h"
#include "car.h"
typedef struct { unsigned b; float ax, ay; } Fr;
extern unsigned long long colWheelPreSeen, colWheelPreSkip, edgeDeathN;
static BotWorld W;
static unsigned long long fnvf(unsigned long long h, float v) { unsigned u; memcpy(&u, &v, 4); for (int i = 0; i < 4; i++) { h ^= (u >> (8 * i)) & 255u; h *= 1099511628211ULL; } return h; }
static unsigned long long fcar(unsigned long long h, const Car *c) { h = fnvf(h, c->x); h = fnvf(h, c->y); h = fnvf(h, c->z); h = fnvf(h, c->v); h = fnvf(h, c->h); h = fnvf(h, c->pitch); h = fnvf(h, c->roll); return h; }
// отпечаток движения: все машины (игрок, миссии, трафик) и Гомер покадрово; bwHash в миссиях зависит от мусора в структурах и между запусками разный
static unsigned long long fpWorld(unsigned long long h) {
  h = fcar(h, &W.car); h = fnvf(h, W.homer.x); h = fnvf(h, W.homer.z);
  for (int c = 0; c < W.msn.cars.n; c++) if (W.msn.cars.c[c].on) h = fcar(h, &W.msn.cars.c[c].car);
  Traffic *t = (Traffic *)bwTraffic(); if (t && t->hd) for (int j = 0; j < t->maxCars; j++) if (t->car[j].mode != TRM_OFF) h = fcar(h, &t->car[j].car);
  return h;
}
int main(int argc, char **argv) {
  if (argc < 7 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "usage: mcrprof LEVEL HOMER MSN INPUT MISSION REPS\n"); return 2; }
  int mi = atoi(argv[5]), reps = atoi(argv[6]); bwNew(&W); if (!W.haveMsn) return 3;
  msn_start_mission(&W.msn.rt, mi, 0);
  Fr *f = 0; int n = 0, cap = 0; char ln[256]; FILE *in = fopen(argv[4], "r"); if (!in) return 4;
  while (fgets(ln, sizeof ln, in)) { if (ln[0] == '#') continue; int k; unsigned b; float ax, ay; if (sscanf(ln, "%d %x %f %f", &k, &b, &ax, &ay) != 4) continue;
    for (int i = 0; i < k; i++) { if (n == cap) { cap = cap ? cap * 2 : 4096; f = realloc(f, sizeof(Fr) * (size_t)cap); } f[n++] = (Fr){b, ax, ay}; } }
  fclose(in);
  if (getenv("MCRPROF_INFO")) { const ColWorld *cw = bwCol(); fprintf(stderr, "коллизия: сетка %dx%d клеток по %.1f м, треугольников %u, ящиков %u, цилиндров %u, заборов %u, ссылок %u (%.1f МБ), в клетке в среднем %.1f\n", cw->W, cw->H, 1.0 / cw->inv, cw->ntri, cw->nbox, cw->ncyl, cw->nseg, cw->nref, cw->nref * 4 / 1048576.0, (double)cw->nref / ((double)cw->W * cw->H)); }
  BotSnap s; bwSaveAlloc(&W, &s); bwSave(&W, &s);
  struct timespec t0, t1; clock_gettime(CLOCK_MONOTONIC, &t0); unsigned long long h = 1469598103934665603ULL; int fp = getenv("MCRPROF_FP") != 0; if (getenv("MCRPROF_OLD")) colWheelPreOld = 1; if (getenv("MCRPROF_EDGE_OLD")) carEdgeDeathOld = 1; double ncars = 0; long frames = 0;
  for (int r = 0; r < reps; r++) {
    bwLoad(&W, &s);
    for (int i = 0; i < n; i++) { bwStep(&W, f[i].b, f[i].ax, f[i].ay); frames++; if (fp) h = fpWorld(h); for (int c = 0; c < W.msn.cars.n; c++) if (W.msn.cars.c[c].on) ncars += 1; }
  }
  clock_gettime(CLOCK_MONOTONIC, &t1); double us = ((t1.tv_sec - t0.tv_sec) * 1e9 + (t1.tv_nsec - t0.tv_nsec)) / 1e3;
  printf("кадров %ld, всего %.1f мкс на кадр, машин миссии в среднем %.2f, отпечаток движения %016llx, колесо-стена: рассмотрено %llu, отсеяно %llu, край принят из-за DEATH %llu\n", frames, us / (double)frames, ncars / (double)frames, fp ? h : 0ULL, colWheelPreSeen, colWheelPreSkip, edgeDeathN);
  return 0;
}
