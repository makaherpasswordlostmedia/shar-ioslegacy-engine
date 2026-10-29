// city984 — общий стенд езды по городу L3–L7 (№984, окно «Оптимизация», 25.10): автопилот теста (viewer/smkpilot.h, тот же код, что «flag drive» в туре) едет по сети дорог
// трафика; несколько маршрутов на уровень (точки на полосах трафика, детерминированный seed); профиль фаз кадра; след машины для сравнения «до/после» (побитно или с допуском).
//   city984 LEVEL PLAYER MSN [--routes N] [--route K] [--secs S] [--seed X] [--trace ПАПКА] [--prof]
//   LEVEL PLAYER MSN — как у других ботов (level.shr, player.shr/homer.shr, levelNN.msn); N маршрутов (по умолчанию 6), K — один; S секунд езды (по умолчанию 60 с = 3600 кадров по 1/60 с)
// Вывод: строка «ROUTE» на маршрут (старт, дистанция, застревания, отпечаток следа, хэш мира, мкс на кадр по фазам при --prof), последняя строка «CITY984 OK/FAIL».
// След (--trace): ПАПКА/L<lv>_r<k>.tsv, строка на кадр: x y z h v w0 w1 w2 vx vy vz (float как %.9g — достаточно для побитного сравнения). Сравнение — tools/bots/city984.sh cmp.
// Цена фаз на Маке ×5,8 ≈ PSP (правило окна «Оптимизация»; точное только для сравнения до/после на одних данных).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <sys/stat.h>
#include "world.h"
#include "smkpilot.h"
static BotWorld W;
static uint64_t fnv(uint64_t h, const void *p, size_t n) { const unsigned char *b = p; for (size_t i = 0; i < n; i++) { h ^= b[i]; h *= 1099511628211ull; } return h; }
static int laneStart(const Traffic *t, int k, int n, unsigned seed, float *x, float *z, float *h) {   // k-я из n точек, равномерно по точкам полос; курс — по ходу полосы
  const TrHeader *hd = t->hd; unsigned total = 0; for (unsigned r = 0; r < hd->nRoad; r++) total += t->road[r].nPt * t->road[r].lanes;
  if (!total) return 0;
  unsigned want = (unsigned)(((unsigned long long)total * (2u * (unsigned)k + 1u)) / (2u * (unsigned)n) + (seed * 7919u) % 97u) % total, acc = 0;
  for (unsigned r = 0; r < hd->nRoad; r++) { const TrRoad *R = &t->road[r]; unsigned cnt = R->nPt * R->lanes; if (!cnt) continue;
    if (want < acc + cnt) { unsigned o = want - acc, lane = o / R->nPt, i = o % R->nPt; if (i + 1 >= R->nPt && i > 0) i--; if (i + 1 >= R->nPt) return 0;
      const TrPt *a = &t->pt[R->firstPt + lane * R->nPt + i], *b = &t->pt[R->firstPt + lane * R->nPt + i + 1]; *x = a->x; *z = a->z; *h = atan2f(b->x - a->x, b->z - a->z); return 1; }
    acc += cnt; }
  return 0;
}
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "usage: city984 LEVEL PLAYER MSN [--routes N] [--route K] [--secs S] [--seed X] [--trace DIR] [--prof]\n"); return 2; }
  int nr = 6, only = -1, prof = 0; float secs = 60.f; unsigned seed = 1; const char *trace = 0;
  for (int i = 4; i < argc; i++) {
    if (!strcmp(argv[i], "--routes") && i + 1 < argc) nr = atoi(argv[++i]); else if (!strcmp(argv[i], "--route") && i + 1 < argc) only = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--secs") && i + 1 < argc) secs = (float)atof(argv[++i]); else if (!strcmp(argv[i], "--seed") && i + 1 < argc) seed = (unsigned)atoi(argv[++i]);
    else if (!strcmp(argv[i], "--trace") && i + 1 < argc) trace = argv[++i]; else if (!strcmp(argv[i], "--prof")) prof = 1; }
  if (trace) mkdir(trace, 0777);
  int lvl = bwLevel(), bad = 0; unsigned long long totF = 0, totNs = 0, phase[8] = {0}; double distAll = 0;
  for (int k = 0; k < nr; k++) {
    if (only >= 0 && k != only) continue;
    bwNew(&W); Traffic *t = (Traffic *)bwTraffic(); if (!t || !t->hd) { printf("ROUTE L%d r%d: нет трафика\n", lvl, k); bad++; continue; }
    float sx, sz, sh, gy; if (!laneStart(t, k, nr, seed, &sx, &sz, &sh)) { printf("ROUTE L%d r%d: нет точки полосы\n", lvl, k); bad++; continue; }
    colGround(bwCol(), sx, sz, 80.f, -1e6f, &gy, 0); bwPlace(&W, sx, gy + .3f, sz, sh);
    for (int f = 0; f < 60; f++) bwStep(&W, 0, 0.f, 0.f);
    SmkPilot P; smkPilotInit(&P, seed * 1000u + (unsigned)k + 1u, 16.f); P.props = &W.props; P.sp = &W.sp; P.lx = W.car.x; P.lz = W.car.z;
    FILE *tf = 0; if (trace) { char fn[512]; snprintf(fn, sizeof fn, "%s/L%d_r%d.tsv", trace, lvl, k); tf = fopen(fn, "w"); }
    uint64_t th = 1469598103934665603ull, trh = 1469598103934665603ull; int frames = (int)(secs * 60.f); float x0 = W.car.x, z0 = W.car.z; double lowT = 0;
    memset(bwPhaseNs, 0, sizeof bwPhaseNs); bwProf = prof;
    struct timespec c0, c1; clock_gettime(CLOCK_MONOTONIC, &c0);
    for (int f = 0; f < frames; f++) {
      CarInput in; smkPilotStep(&P, t, &W.car, 1.f / 60.f, &in);
      unsigned b = 0; if (in.throttle > .5f) b |= GP_R; if (in.brake > .1f) b |= GP_L; if (in.handbrake > .5f) b |= GP_SQUARE;
      bwStep(&W, b, in.steer, 0.f);
      float s[11] = {W.car.x, W.car.y, W.car.z, W.car.h, W.car.v, W.car.w[0], W.car.w[1], W.car.w[2], W.car.vel[0], W.car.vel[1], W.car.vel[2]}; th = fnv(th, s, sizeof s);
      for (int j = 0; j < t->maxCars; j++) { const TrCar *tc = &t->car[j]; if (tc->mode == TRM_OFF) continue; float q[3] = {tc->car.x, tc->car.z, (float)tc->mode}; trh = fnv(trh, q, sizeof q); }   // трафик: машины в кадре (поведение окружения тоже должно совпасть)
      if (tf) fprintf(tf, "%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t%.9g\t%.9g\n", s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], s[9], s[10]);
      if (fabsf(W.car.v) < 1.f) lowT += 1.0 / 60; }
    clock_gettime(CLOCK_MONOTONIC, &c1); bwProf = 0; if (tf) fclose(tf);
    unsigned long long ns = (unsigned long long)(c1.tv_sec - c0.tv_sec) * 1000000000ull + (unsigned long long)(c1.tv_nsec - c0.tv_nsec);
    totF += (unsigned)frames; totNs += ns; distAll += P.dist; for (int i = 0; i < 8; i++) phase[i] += bwPhaseNs[i];
    printf("ROUTE L%d r%d: старт (%.0f,%.0f) курс %.2f, %.0f с: дистанция %.0f м, застреваний %d, стояла %.1f с, урон %.2f, след %016llx, трафик %016llx, %.1f мкс/кадр", lvl, k, sx, sz, sh, secs, P.dist, P.stuckN, lowT, W.car.damage,
           (unsigned long long)th, (unsigned long long)trh, (double)ns / 1000.0 / frames);
    if (prof) { printf(" | фазы мкс/кадр: машина %.1f, мир %.1f, респавн/комнаты %.1f, трафик %.1f, H&R %.1f", bwPhaseNs[0] / 1000.0 / frames, bwPhaseNs[1] / 1000.0 / frames, bwPhaseNs[2] / 1000.0 / frames, bwPhaseNs[3] / 1000.0 / frames, bwPhaseNs[4] / 1000.0 / frames); }
    printf("\n"); (void)x0; (void)z0;
    if (P.dist < 150.f) bad++;
  }
  if (totF) { printf("ИТОГ L%d: кадров %llu, %.1f мкс/кадр", lvl, totF, (double)totNs / 1000.0 / (double)totF);
    if (prof) printf(" | фазы мкс/кадр: машина %.1f, мир %.1f, респавн/комнаты %.1f, трафик %.1f, H&R %.1f", phase[0] / 1000.0 / totF, phase[1] / 1000.0 / totF, phase[2] / 1000.0 / totF, phase[3] / 1000.0 / totF, phase[4] / 1000.0 / totF);
    printf(", дистанция %.0f м\n", distAll); }
  printf("CITY984 %s\n", bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
