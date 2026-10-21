// Навигатор (пункт Б1, docs/БОТЫ-ИГРОКИ_2026-09-28.md §3.1): самый быстрый путь из A в B настоящей ездой в игре без экрана.
// 1) грубый путь A* по графу дорог уровня (roads.bin: отрезки 0x3000002, оба направления, стыки до 1.5 м и перекрёстки до 12 м);
// 2) водитель-правило с числами (упреждение, скорости, торможение, руль, ручник) едет по пути со сдвигами опорных точек вбок —
//    так находятся срезки через дворы; 3) эволюция: 64 варианта (числа водителя + сдвиги точек), лучшие 8 скрещиваются и мутируют.
// Цель засчитана, только если машина реально доехала: ближе 6 м по плоскости и ±2.5 м по высоте. Телепорта нет, старт — bwPlace.
// Повтор: бинарник + ввод по кадрам (файл для game_headless --input, старт в точке A). Без AI и сети.
//   nav LEVEL HOMER ROADS --pair AX AZ BX BY BZ [--gens 200] [--pop 64] [--out DIR] [--seed S]
//   nav LEVEL HOMER ROADS --gate [--out DIR]     гейты Б1: цель внутри дома -> «недостижимо»; короткий маршрут от спавна находится
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

#include "navgraph.h"   // граф дорог, A*, водитель по опорным точкам (общий с миссионером)

// ------------------------------------------------------------------ водитель по пути
typedef struct { float par[NPAR]; float off[MAXWP]; } Genome;   // числа водителя + сдвиг опорных точек вбок, м
// par: 0 упреждение базовое м, 1 упреждение на м/с, 2 скорость на прямой м/с, 3 скорость в повороте м/с, 4 торможение: запас по скорости,
//      5 усиление руля, 6 угол ошибки для ручника (рад)
static P3 wp[MAXWP]; static int nwp; static P3 goal; static float tmax, tscale = 1.f;
#ifndef NAV_REACH_R
#define NAV_REACH_R 6.f   // отрицательный контроль гейта: -DNAV_REACH_R=600 — «доехал» издалека, дом обязан стать «достижимым» -> FAIL
#endif
static uint32_t rs = 1;
static float fr(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return (rs >> 8) * (1.f / 16777216.f); }
static float gauss(void) { float u = fr() + 1e-7f, v = fr(); return sqrtf(-2.f * logf(u)) * cosf(6.2831853f * v); }
static BotWorld W; static BotSnap S0; static int lastOk, lastSame;   // итог последнего route(): доехал; повтор в тот же кадр (или оба не доехали)
typedef struct { unsigned b; float ax; } In;
static In *rec; static int nrec;
// заезд: -> время до цели (с) или tmax + остаток пути; *reachedAt — кадр достижения (-1 нет); rec — ввод по кадрам
static float drive(const Genome *G, int *reachedAt, int keep, float *stuckXZ, int *nstuck) {
  bwLoad(&W, &S0);
  P3 q[MAXWP];   // опорные точки со сдвигом вбок (к соседям)
  for (int i = 0; i < nwp; i++) {
    int a = i > 0 ? i - 1 : 0, b = i + 1 < nwp ? i + 1 : nwp - 1; float dx = wp[b].x - wp[a].x, dz = wp[b].z - wp[a].z, l = hypotf(dx, dz) + 1e-3f;
    float o = (i == 0 || i == nwp - 1) ? 0.f : G->off[i];
    q[i] = (P3){wp[i].x + dz / l * o, wp[i].y, wp[i].z - dx / l * o};
  }
  int seg = 0, frames = (int)(tmax * 60); *reachedAt = -1; nrec = 0; if (nstuck) *nstuck = 0;
  float slowT = 0.f;
  for (int f = 0; f < frames; f++) {
    Car *c = &W.car; unsigned b; float ax; navSteer(q, nwp, &seg, c, G->par, &b, &ax);
    if (keep) { rec[nrec++] = (In){b, ax}; }
    bwStep(&W, b, ax, 0.f);
    float dx = c->x - goal.x, dz = c->z - goal.z;
    if (dx * dx + dz * dz < NAV_REACH_R * NAV_REACH_R && (NAV_REACH_R > 100.f || fabsf(c->y - goal.y) < 2.5f)) { *reachedAt = f; return (f + 1) / 60.f; }
    if (fabsf(c->v) < 2.f) { slowT += BW_DT; if (slowT > 1.f && stuckXZ && nstuck && *nstuck < 64 && ((int)(slowT * 60) % 60 == 0)) {
      stuckXZ[2 * *nstuck] = c->x; stuckXZ[2 * *nstuck + 1] = c->z; (*nstuck)++; } } else slowT = 0.f;
  }
  // не доехал: остаток по опорным точкам от ближайшей
  Car *c = &W.car; float rem = hypotf(c->x - q[seg < nwp - 1 ? seg + 1 : nwp - 1].x, c->z - q[seg < nwp - 1 ? seg + 1 : nwp - 1].z);
  for (int i = seg + 1; i + 1 < nwp; i++) rem += hypotf(q[i + 1].x - q[i].x, q[i + 1].z - q[i].z);
  return tmax + rem / 5.f;
}
static int cmpFit(const void *a, const void *b) { float x = *(const float *)a, y = *(const float *)b; return x < y ? -1 : x > y; }
typedef struct { float fit; Genome g; } Ind;
static int cmpInd(const void *a, const void *b) { return cmpFit(&((const Ind *)a)->fit, &((const Ind *)b)->fit); }

// один маршрут: -> 1 доехал; печатает строку и пишет файл повтора
static int route(float ax, float az, float bx, float by, float bz, int gens, int pop, const char *out, const char *tag, float *bestT, float *baseT) {
  float ay; if (!colGround(bwCol(), ax, az, 1e4f, -1e4f, &ay, 0)) { printf("%s: нет земли в A\n", tag); return 0; }
  int s = nearestNode(ax, ay, az), g = nearestNode(bx, by, bz), path[MAXWP * 4];
  int n = astar(s, g, path, MAXWP * 4);
  nwp = 0; wp[nwp++] = (P3){ax, ay, az};
  if (n) { int step = n > MAXWP - 3 ? (n + MAXWP - 4) / (MAXWP - 3) : 1; for (int i = 0; i < n && nwp < MAXWP - 1; i += step) wp[nwp++] = node[path[i]]; }
  wp[nwp++] = (P3){bx, by, bz}; goal = wp[nwp - 1];
  float len = 0; for (int i = 0; i + 1 < nwp; i++) len += hypotf(wp[i + 1].x - wp[i].x, wp[i + 1].z - wp[i].z);
  tmax = (20.f + len / 6.f) * tscale;
  bwFree(&W); bwNew(&W); bwPlace(&W, ax, ay, az, atan2f(wp[1].x - ax, wp[1].z - az));
  for (int k = 0; k < 30; k++) bwStep(&W, 0, 0, 0);   // машина села на колёса
  bwSave(&W, &S0);
  Ind *P = calloc((size_t)pop, sizeof(Ind)), *C = calloc((size_t)pop, sizeof(Ind)); int ra;
  for (int i = 0; i < pop; i++) {
    for (int k = 0; k < NPAR; k++) P[i].g.par[k] = i == 0 ? PAR0[k] : fmaxf(PARLO[k], fminf(PARHI[k], PAR0[k] * (1.f + .25f * gauss())));
    for (int k = 0; k < nwp; k++) P[i].g.off[k] = i == 0 ? 0.f : 3.f * gauss() * (fr() < .3f);
    P[i].fit = drive(&P[i].g, &ra, 0, 0, 0);
  }
  *baseT = P[0].fit;   // водитель по умолчанию, без сдвигов
  qsort(P, (size_t)pop, sizeof(Ind), cmpInd);
  for (int gen = 0; gen < gens; gen++) {
    int elite = pop / 8 > 1 ? pop / 8 : 1;
    for (int i = 0; i < pop; i++) {
      if (i < elite) { C[i] = P[i]; continue; }
      const Genome *A = &P[(int)(fr() * elite)].g, *B = &P[(int)(fr() * elite)].g; Genome *K = &C[i].g;
      for (int k = 0; k < NPAR; k++) { K->par[k] = fr() < .5f ? A->par[k] : B->par[k]; if (fr() < .3f) K->par[k] = fmaxf(PARLO[k], fminf(PARHI[k], K->par[k] * (1.f + .12f * gauss()))); }
      for (int k = 0; k < nwp; k++) { K->off[k] = fr() < .5f ? A->off[k] : B->off[k]; if (fr() < .15f) K->off[k] = fmaxf(-12.f, fminf(12.f, K->off[k] + 2.5f * gauss())); }
      C[i].fit = drive(K, &ra, 0, 0, 0);
    }
    Ind *t = P; P = C; C = t; qsort(P, (size_t)pop, sizeof(Ind), cmpInd);
  }
  float stuck[128]; int ns = 0;
  float best = drive(&P[0].g, &ra, 1, stuck, &ns);
  *bestT = best; int ok = ra >= 0;
  // повтор ввода: записанные нажатия из того же старта обязаны доехать в тот же кадр
  bwLoad(&W, &S0); int rr = -1;
  for (int f = 0; f < nrec; f++) { bwStep(&W, rec[f].b, rec[f].ax, 0.f); float dx = W.car.x - goal.x, dz = W.car.z - goal.z;
    if (rr < 0 && dx * dx + dz * dz < NAV_REACH_R * NAV_REACH_R && (NAV_REACH_R > 100.f || fabsf(W.car.y - goal.y) < 2.5f)) rr = f; }
  if (out) {   // файл повтора: старт (bwPlace + 30 кадров стоя) и ввод по кадрам
    char fn[512]; snprintf(fn, sizeof fn, "%s/%s.in", out, tag); FILE *fo = fopen(fn, "w");
    if (fo) { fprintf(fo, "# nav %s: A %.2f %.2f -> B %.2f %.2f %.2f; start: --start %.9g %.9g %.9g %.9g; then 30 idle frames\n", tag, ax, az, bx, by, bz, ax, ay, az,
                      atan2f(wp[1].x - ax, wp[1].z - az));
      fprintf(fo, "30 0 0 0\n");   // 30 кадров стоя после bwPlace — как снимок S0, с которого ехали маршрут и проверка
      for (int i = 0; i < nrec; ) { int j = i; while (j < nrec && rec[j].b == rec[i].b && rec[j].ax == rec[i].ax) j++; fprintf(fo, "%d %x %.9g 0\n", j - i, rec[i].b, rec[i].ax); i = j; }
      fclose(fo); }
  }
  char t0[32], t1[32];
  if (*baseT <= tmax) snprintf(t0, sizeof t0, "%.2f с", *baseT); else snprintf(t0, sizeof t0, "не доехал");
  if (ok) snprintf(t1, sizeof t1, "%.2f с", best); else snprintf(t1, sizeof t1, "не доехал");
  printf("R\t%s\t%.1f\t%.1f\t%.1f\t%.1f\t%.1f\t%.0f\t%.0f\t%s\t%s\t%s\t%s\t%d", tag, ax, az, bx, by, bz, hypotf(bx - ax, bz - az), len,
         ok ? "доехал" : "НЕДОСТИЖИМО", t0, t1, rr != ra ? "РАЗОШЁЛСЯ" : ok ? "тот_же_кадр" : "не_доехал_и_в_повторе", ns);   // «тот же кадр» — только у доехавших
  for (int i = 0; i < ns; i++) printf("\t%.1f,%.1f", stuck[2 * i], stuck[2 * i + 1]);
  printf("\n");
  free(P); free(C);
  lastOk = ok; lastSame = rr == ra;
  return ok && rr == ra;
}

int main(int argc, char **argv) {
  if (argc < 5) { fprintf(stderr, "usage: nav LEVEL HOMER ROADS --pair AX AZ BX BY BZ | --gate [--gens N --pop N --out DIR --seed S]\n"); return 2; }
  if (bwData(argv[1], argv[2], 0)) { fprintf(stderr, "nav: нет данных\n"); return 2; }
  loadRoads(argv[3]);
  int gens = 200, pop = 64; const char *out = 0; float pr[5]; int pair = 0, gate = 0, table = 0, part = 0, parts = 1;
  for (int i = 4; i < argc; i++) {
    if (!strcmp(argv[i], "--gens") && i + 1 < argc) gens = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--pop") && i + 1 < argc) pop = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
    else if (!strcmp(argv[i], "--seed") && i + 1 < argc) rs = (uint32_t)strtoul(argv[++i], 0, 10) | 1;
    else if (!strcmp(argv[i], "--gate")) gate = 1;
    else if (!strcmp(argv[i], "--tscale") && i + 1 < argc) tscale = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--table") && i + 3 < argc) { table = atoi(argv[++i]); part = atoi(argv[++i]); parts = atoi(argv[++i]); }
    else if (!strcmp(argv[i], "--pair") && i + 5 < argc) { for (int k = 0; k < 5; k++) pr[k] = (float)atof(argv[++i]); pair = 1; }
  }
  rec = malloc(sizeof(In) * 60 * 600);
  bwNew(&W); bwSaveAlloc(&W, &S0);
  printf("граф дорог: %d отрезков, %d узлов\n", nroad, nnode);
  float bt, b0;
  if (pair) return route(pr[0], pr[1], pr[2], pr[3], pr[4], gens, pop, out, "pair", &bt, &b0) ? 0 : 1;
  if (table) {   // таблица A->B: пары узлов дорог 100–400 м по прямой, порядок от seed; часть part из parts
    uint32_t keep = rs; int made = 0;
    for (int k = 0; made < table && k < table * 50; k++) {
      int a = (int)(fr() * nnode), b = (int)(fr() * nnode); float d = hypotf(node[a].x - node[b].x, node[a].z - node[b].z);
      if (d < 100.f || d > 400.f) continue;
      if (made++ % parts != part) continue;
      uint32_t save = rs; rs = keep ^ (uint32_t)(made * 2654435761u); if (!rs) rs = 1;   // своя случайность на маршрут: не зависит от частей
      char tag[32]; snprintf(tag, sizeof tag, "r%03d", made - 1);
      route(node[a].x, node[a].z, node[b].x, node[b].y, node[b].z, gens, pop, out, tag, &bt, &b0);
      rs = save; fflush(stdout);
    }
    return 0;
  }
  if (gate) {
    // (а) короткий маршрут от спавна: точка дороги ~150 м по графу от ближайшего к спавну узла -> доехал, повтор тот же кадр
    float sx, sy, sz, sh; bwSpawn(&sx, &sy, &sz, &sh);
    int s = nearestNode(sx, sy, sz), best = -1; float bd = 1e9f;
    for (int i = 0; i < nnode; i++) { float d = hypotf(node[i].x - node[s].x, node[i].z - node[s].z); if (fabsf(d - 150.f) < bd && fabsf(node[i].y - node[s].y) < 3.f) { bd = fabsf(d - 150.f); best = i; } }
    int okA = route(sx, sz, node[best].x, node[best].y, node[best].z, gens, pop, out, "gate_short", &bt, &b0);
    // (б) цель внутри дома: большой ящик COL1 (≥ 6×6 м в плане, выше пола на 3+ м), центр на уровне земли у стены -> недостижимо
    const ColWorld *cw = bwCol(); int hb = -1; float bestD = 1e9f;
    for (unsigned i = 0; i < cw->nbox; i++) {
      const ColBox *B = &cw->box[i]; float ex = fabsf(B->ax[0]) * B->h[0] + fabsf(B->ay[0]) * B->h[1] + fabsf(B->az[0]) * B->h[2];
      float ez = fabsf(B->ax[2]) * B->h[0] + fabsf(B->ay[2]) * B->h[1] + fabsf(B->az[2]) * B->h[2];
      float ey = fabsf(B->ax[1]) * B->h[0] + fabsf(B->ay[1]) * B->h[1] + fabsf(B->az[1]) * B->h[2];
      if (ex < 6.f || ez < 6.f || ey < 2.5f) continue;
      float g; if (!colGround(cw, B->c[0] + ex + 3.f, B->c[2], B->c[1] + ey, B->c[1] - ey - 5.f, &g, 0)) continue;   // рядом с домом есть земля
      if (g < B->c[1] - ey - 1.f || g > B->c[1] - ey + 1.5f) continue;                                               // дом стоит на этой земле
      float d = hypotf(B->c[0] - sx, B->c[2] - sz); if (d < bestD && d > 60.f) { bestD = d; hb = (int)i; }
    }
    int okB = 0;
    if (hb >= 0) {
      const ColBox *B = &cw->box[hb]; float ey = fabsf(B->ax[1]) * B->h[0] + fabsf(B->ay[1]) * B->h[1] + fabsf(B->az[1]) * B->h[2];
      printf("дом: ящик COL1 %d, центр %.1f %.1f %.1f\n", hb, B->c[0], B->c[1], B->c[2]);
      route(sx, sz, B->c[0], B->c[1] - ey + .5f, B->c[2], gens, pop, out, "gate_inside_house", &bt, &b0);
      okB = !lastOk && lastSame;   // недостижима: не доехал ни эволюцией, ни повтором (расхождение повтора — не «недостижима»)
    } else printf("дом для гейта не найден\n");
    printf("гейт Б1: короткий маршрут %s, цель внутри дома %s -> %s\n", okA ? "найден" : "НЕ найден", okB ? "недостижима" : "ДОСТИЖИМА?", okA && okB ? "PASS" : "FAIL");
    return okA && okB ? 0 : 1;
  }
  return 2;
}
