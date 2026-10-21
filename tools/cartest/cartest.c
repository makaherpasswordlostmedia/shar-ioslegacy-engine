// cartest — прогон машины (viewer/car.c + viewer/col.c) ботами по уровню с секцией COL1, на Маке.
//   cartest LEVEL.shr [--roads roads.bin] [--out DIR] [--secs 60] [--seeds 2] [--trace 12] [--pts N] [--start K]
//           [--only K] [--mode road|wild|all] [--quiet]
// Старты — точки тест-прогона движка (main.c benchPoints: сетка 50 м там, где у карты высот есть земля).
// С каждой точки: бот по дорогам (отрезки 0x3000002) и «дикий» бот (газ в пол в стены, назад, волчок, съезды,
// прыжки) с разными зёрнами. Метрики — см. таблицу в конце; трассы худших прогонов — DIR/traces.bin
// (картинки рисует tools/cartest/trace_png.py).
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <time.h>
#include "../../viewer/col.h"
#include "../../viewer/car.h"

#define PI 3.14159265f
#define FPS 60
#define WIN (3 * FPS)          // окно «застрял»: 3 с
#define MAXRUNS 20000

// ------------------------------------------------------------------------------------------------ данные
static unsigned char *file; static size_t fileSize;
static short *hm; static float hox, hoz, hcell; static int hw, hh;
static ColWorld W;
typedef struct { float ax, ay, az, bx, by, bz, hw; } Road;
static Road *roads; static int nroad;
static int *nxtStart, *nxtList;

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static uint32_t rng = 1;
static uint32_t rnd(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
static float frand(void) { return (rnd() >> 8) * (1.f / 16777216.f); }
static float wrapPi(float a) { while (a > PI) a -= 2 * PI; while (a < -PI) a += 2 * PI; return a; }

static void *readAll(const char *p, size_t *n) {
  FILE *f = fopen(p, "rb"); if (!f) return 0;
  fseek(f, 0, SEEK_END); long s = ftell(f); fseek(f, 0, SEEK_SET);
  void *b = malloc(s + 16); if (!b || fread(b, 1, s, f) != (size_t)s) { fclose(f); free(b); return 0; }
  fclose(f); *n = s; return b;
}

static void loadLevel(const char *path) {
  file = readAll(path, &fileSize);
  if (!file || fileSize < 104 || memcmp(file, "SHR7", 4)) { fprintf(stderr, "%s: not SHR7\n", path); exit(2); }
  float *hd = (float *)(file + 12);
  hox = hd[11]; hoz = hd[12]; hcell = hd[13]; hw = *(int *)(hd + 14); hh = *(int *)(hd + 15);
  if (hw <= 0 || hh <= 0 || !isfinite(hcell) || hcell <= 0 ||
      (uint64_t)hw * hh * 8 > fileSize - 104) { fprintf(stderr, "invalid height grid\n"); exit(2); }
  hm = (short *)(file + 104);
  uint32_t pvsOff = *(uint32_t *)(file + 88), colOff = *(uint32_t *)(file + 92);
  if (!colOff || colOff >= fileSize) { fprintf(stderr, "%s: no COL1 (@92)\n", path); exit(2); }
  size_t end = pvsOff > colOff ? pvsOff : fileSize;
  if (end > fileSize) { fprintf(stderr, "invalid section offset\n"); exit(2); }
  for (int k = 96; k <= 100; k += 4) {
    uint32_t off = *(uint32_t *)(file + k);
    if (off > fileSize) { fprintf(stderr, "invalid section offset\n"); exit(2); }
    if (off > colOff && off < end) end = off;
  }
  int r = colInit(&W, file + colOff, (unsigned)(end - colOff));
  if (r) { fprintf(stderr, "colInit: %s\n", colError(r)); exit(1); }
}

static void loadRoads(const char *path) {
  size_t n; float *f = readAll(path, &n);
  if (!f) { fprintf(stderr, "roads: cannot read %s\n", path); exit(1); }
  if (!n || n % sizeof(Road)) { fprintf(stderr, "invalid roads\n"); exit(2); }
  nroad = (int)(n / sizeof(Road)); roads = (Road *)f;
  // следующий отрезок: начало рядом с концом (< 1 м); если нет — перекрёсток: начала в 15 м не назад
  nxtStart = calloc(nroad + 1, sizeof(int)); int cap = nroad * 8; nxtList = malloc(cap * sizeof(int)); int m = 0;
  for (int i = 0; i < nroad; i++) {
    nxtStart[i] = m;
    Road *a = &roads[i]; float dx = a->bx - a->ax, dz = a->bz - a->az, l = sqrtf(dx * dx + dz * dz) + 1e-6f; dx /= l; dz /= l;
    for (int pass = 0; pass < 3 && m == nxtStart[i]; pass++) {
      float lim = pass == 0 ? 1.f : pass == 1 ? 15.f : 25.f;
      for (int j = 0; j < nroad && m < cap; j++) {
        if (j == i) continue;
        Road *b = &roads[j]; float ex = b->ax - a->bx, ez = b->az - a->bz;
        if (ex * ex + ez * ez > lim * lim) continue;
        float qx = b->bx - b->ax, qz = b->bz - b->az, q = sqrtf(qx * qx + qz * qz) + 1e-6f;
        float dot = (dx * qx + dz * qz) / q;
        if (pass == 1 && dot < -0.2f) continue;
        if (pass < 2 && dot < -0.9f && fabsf(b->bx - a->ax) + fabsf(b->bz - a->az) < 4.f) continue;   // обратная полоса
        nxtList[m++] = j;
      }
    }
  }
  nxtStart[nroad] = m;
}

// ------------------------------------------------------------------------------------------------ досягаемость
// заливка от спавна по сетке 2 м: соседняя клетка проходима, если под ней есть земля не выше +1.2 м и не ниже -2 м
// от текущей (едем, а не падаем) и путь между центрами не пересекает забор с лица на изнанку. Стены-ящики не
// учитываются (оценка сверху). Старт «досягаем», если его клетка залита на его высоте (+-2.5 м).
#define RC 2.f
static float *reachY; static int rw, rh; static long reachN;
static void reachFill(float sx, float sy, float sz) {
  rw = (int)(W.W * W.cell / RC); rh = (int)(W.H * W.cell / RC);
  reachY = malloc(sizeof(float) * rw * rh); for (long i = 0; i < (long)rw * rh; i++) reachY[i] = NAN;
  int *q = malloc(sizeof(int) * rw * rh); long qh = 0, qt = 0; float g;
  int cx = (int)((sx - W.ox) / RC), cz = (int)((sz - W.oz) / RC);
  if (!colGround(&W, sx, sz, sy + 2.f, -1e6f, &g, 0)) return;
  reachY[cz * rw + cx] = g; q[qt++] = cz * rw + cx;
  static const int dx[4] = {1, -1, 0, 0}, dz[4] = {0, 0, 1, -1};
  while (qh < qt) {
    int c = q[qh++], x = c % rw, z = c / rw; float h = reachY[c];
    float px = W.ox + (x + .5f) * RC, pz = W.oz + (z + .5f) * RC;
    for (int k = 0; k < 4; k++) {
      int nx = x + dx[k], nz = z + dz[k]; if (nx < 0 || nz < 0 || nx >= rw || nz >= rh) continue;
      int n = nz * rw + nx; if (!isnan(reachY[n])) continue;
      float qx = W.ox + (nx + .5f) * RC, qz = W.oz + (nz + .5f) * RC;
      if (!colGround(&W, qx, qz, h + 1.2f, -1e6f, &g, 0) || g < h - 2.f) continue;
      if (colCrossFence(&W, px, pz, qx, qz, 0, 0)) continue;
      reachY[n] = g; q[qt++] = n;
    }
  }
  reachN = qt; free(q);
}
static int reachable(float x, float y, float z) {
  int cx = (int)((x - W.ox) / RC), cz = (int)((z - W.oz) / RC);
  if (!reachY || cx < 0 || cz < 0 || cx >= rw || cz >= rh) return 0;
  float r = reachY[cz * rw + cx]; return !isnan(r) && fabsf(r - y) < 2.5f;
}

// ------------------------------------------------------------------------------------------------ старты
#define MAXBP 1024
static float bpx[MAXBP], bpy[MAXBP], bpz[MAXBP]; static int nbp;
static void benchPoints(void) {   // как main.c benchPoints()
  int st = (int)(50.f / hcell); nbp = 0;
  for (int gz = st / 2, row = 0; gz < hh; gz += st, row++)
    for (int j = 0; j < hw / st + 1; j++) {
      int gx = st / 2 + (row & 1 ? (hw / st - j) : j) * st;
      if (gx < 0 || gx >= hw || nbp >= MAXBP) continue;
      short *c = hm + ((size_t)gz * hw + gx) * 4; int lo = 32767;
      for (int i = 0; i < 4; i++) if (c[i] != -32768 && c[i] < lo) lo = c[i];
      if (lo == 32767) continue;
      bpx[nbp] = hox + (gx + .5f) * hcell; bpz[nbp] = hoz + (gz + .5f) * hcell; bpy[nbp] = lo * .01f; nbp++;
    }
}
// внутри петли заборов (непроезжее) — чётность пересечений луча +x
static int insideFences(float x, float z) {
  int c = 0;
  for (uint32_t i = 0; i < W.nseg; i++) {
    const ColSeg *s = &W.seg[i];
    float az = s->a[1], bz = s->b[1];
    if ((az > z) == (bz > z)) continue;
    float t = (z - az) / (bz - az), xi = s->a[0] + t * (s->b[0] - s->a[0]);
    if (xi > x) c ^= 1;
  }
  return c;
}
static int nearestRoad(float x, float z, float h, float maxd) {
  int best = -1; float bd = maxd * maxd;
  float fx = sinf(h), fz = cosf(h);
  for (int i = 0; i < nroad; i++) {
    Road *r = &roads[i]; float dx = r->bx - r->ax, dz = r->bz - r->az, l2 = dx * dx + dz * dz + 1e-9f;
    float t = ((x - r->ax) * dx + (z - r->az) * dz) / l2; t = t < 0 ? 0 : t > 1 ? 1 : t;
    float px = r->ax + dx * t - x, pz = r->az + dz * t - z, d2 = px * px + pz * pz;
    if (h < 99.f) { float l = sqrtf(l2); if ((dx * fx + dz * fz) / l < -0.3f) d2 += 400.f; }   // против курса — хуже
    if (d2 < bd) { bd = d2; best = i; }
  }
  return best;
}

// ------------------------------------------------------------------------------------------------ боты
typedef struct {
  int mode;            // 0 дорога, 1 дикий
  int cur, nxt;
  float stuckT, backT, backSteer, lastX, lastZ, lastT; int lastCmd, backDir;
  int wmode; float wT, wSteer, wPhase, tx, tz;
} Bot;

static void roadTarget(Bot *b, const Car *c, float L, float *tx, float *tz, float *turnAhead, float *distJ) {
  Road *r = &roads[b->cur];
  float dx = r->bx - r->ax, dz = r->bz - r->az, len = sqrtf(dx * dx + dz * dz) + 1e-6f; dx /= len; dz /= len;
  float t = (c->x - r->ax) * dx + (c->z - r->az) * dz; if (t < 0) t = 0;
  float rem = len - t;
  *distJ = rem;
  Road *n = &roads[b->nxt];
  float ex = n->bx - n->ax, ez = n->bz - n->az, l2 = sqrtf(ex * ex + ez * ez) + 1e-6f; ex /= l2; ez /= l2;
  *turnAhead = fabsf(wrapPi(atan2f(ex, ez) - atan2f(dx, dz)));
  if (rem >= L) { *tx = r->ax + dx * (t + L); *tz = r->az + dz * (t + L); }
  else { float k = L - rem; if (k > l2) k = l2; *tx = n->ax + ex * k; *tz = n->az + ez * k; }
}
static int pickNext(int cur) {
  int a = nxtStart[cur], b = nxtStart[cur + 1];
  if (a == b) { int next = nearestRoad(roads[cur].bx, roads[cur].bz, 100.f, 60.f); return next < 0 ? cur : next; }
  return nxtList[a + (int)(rnd() % (unsigned)(b - a))];
}

// cmd: +1 вперёд, -1 назад, 0 ничего
static int botStep(Bot *b, const Car *c, CarInput *in, float t) {
  *in = (CarInput){0};
  // разворот из тупика (оба бота): 1.5 с без продвижения на газу — 1.2 с назад с рулём в другую сторону
  if (t - b->lastT >= 0.5f) {
    float dx = c->x - b->lastX, dz = c->z - b->lastZ;
    if (dx * dx + dz * dz < 0.3f * 0.3f && b->backT <= 0) b->stuckT += t - b->lastT; else b->stuckT = 0;
    b->lastX = c->x; b->lastZ = c->z; b->lastT = t;
    if (b->stuckT >= 1.5f) { b->backT = 1.2f; b->backSteer = c->steer > 0 ? -1.f : 1.f; b->stuckT = 0; b->backDir = b->lastCmd < 0 ? 1 : -1; }
  }
  if (b->backT > 0) {   // выбираемся в другую сторону: назад, а если застряли задним ходом — вперёд
    b->backT -= 1.f / FPS; in->steer = b->backSteer;
    if (b->backDir > 0) { in->throttle = 1; return 1; }
    in->brake = 1; return c->v <= 0.5f ? -1 : 0;
  }
  if (b->mode == 0) {
    float L = 5.f + 0.35f * fabsf(c->v), tx, tz, turn, dj;
    Road *r = &roads[b->cur];
    // дошли до конца отрезка — следующий
    float ex = r->bx - c->x, ez = r->bz - c->z;
    float dx = r->bx - r->ax, dz = r->bz - r->az;
    if (ex * ex + ez * ez < 16.f || ((c->x - r->bx) * dx + (c->z - r->bz) * dz) > 0) { b->cur = b->nxt; b->nxt = pickNext(b->cur); }
    roadTarget(b, c, L, &tx, &tz, &turn, &dj);
    // ушли далеко от дороги — ближайшая
    float px = tx - c->x, pz = tz - c->z;
    if (px * px + pz * pz > 40.f * 40.f) { b->cur = nearestRoad(c->x, c->z, c->h, 200.f); if (b->cur < 0) b->cur = 0; b->nxt = pickNext(b->cur); roadTarget(b, c, L, &tx, &tz, &turn, &dj); }
    float e = wrapPi(atan2f(tx - c->x, tz - c->z) - c->h);
    in->steer = fmaxf(-1.f, fminf(1.f, -e * 2.2f));
    float vt = 26.f;
    if (turn > 0.5f && dj < 35.f) vt = 11.f;
    if (fabsf(e) > 0.5f) vt = 9.f;
    if (c->v < vt) in->throttle = 1; else if (c->v > vt + 3.f) in->brake = 1;
    return in->throttle > 0 ? 1 : 0;
  }
  if (b->mode == 2) { in->throttle = 1; in->steer = 0; return 1; }   // таран: газ в пол прямо в цель
  // дикий: режимы по 1..4 с
  b->wT -= 1.f / FPS;
  if (b->wT <= 0) {
    b->wmode = (int)(rnd() % 7u); b->wT = 1.f + 3.f * frand(); b->wSteer = frand() * 2.f - 1.f; b->wPhase = frand() * 6.f;
    float a = frand() * 2 * PI, d = 20.f + 60.f * frand(); b->tx = c->x + sinf(a) * d; b->tz = c->z + cosf(a) * d;
  }
  switch (b->wmode) {
  case 0: in->throttle = 1; in->steer = b->wSteer * 0.3f; return 1;                           // газ в пол почти прямо
  case 1: in->throttle = 1; in->steer = sinf(t * 3.f + b->wPhase); return 1;                   // слалом
  case 2: in->throttle = 1; in->steer = b->wSteer > 0 ? 1.f : -1.f; return 1;                 // волчок
  case 3: in->brake = 1; in->steer = b->wSteer; return c->v <= 0.5f ? -1 : 0;                 // назад
  case 4: if (c->v > 1.f) in->brake = 1; in->steer = b->wSteer; return 0;                      // торможение
  default: {                                                                                   // в точку — в стены
    float e = wrapPi(atan2f(b->tx - c->x, b->tz - c->z) - c->h);
    in->steer = fmaxf(-1.f, fminf(1.f, -e * 3.f)); in->throttle = 1; return 1;
  }
  }
}

// ------------------------------------------------------------------------------------------------ прогон
typedef struct { float x, z, y, v; uint8_t fl; } TP;
enum { F_FALL = 1, F_EXIT = 2, F_PEN = 4, F_STUCK = 8, F_REC = 16, F_REV = 32, F_AIR = 64, F_HIT = 128 };
typedef struct {
  int pt, mode, seed, reach; float sx, sz, sh;
  int falls, noSurf, exits, penEv, stuck, blocked, recov, reverts, frames;
  float maxPen, penTime, maxHit, dist, airTime, maxAir;
  double cpu, cpuMax;
  float stuckX, stuckZ; int stuckF, firstRevF;
  double score;
} Run;
static Run runs[MAXRUNS]; static int nruns;
typedef struct { double el; int run, frame, rev, rec, air; float dt; } Slow; static Slow slow[10]; static int nslow;
static long ctypeN[4], hitTypeN[4]; static double cpuAll, cpuMaxAll, cpuTrim; static long updAll, revWhyN[64], nTrim, nOut; static long cpuHist[400];   // гистограмма по 0.25 мкс

static TP *trBuf; static int trN;
typedef struct { int run; int n; TP *tp; } Trace;
static Trace worst[64]; static int nworst, wantTrace = 12;

static void keepTrace(int ri) {
  Run *r = &runs[ri];
  if (wantTrace <= 0) return;
  int slot = -1;
  if (nworst < wantTrace) slot = nworst++;
  else { int m = 0; for (int i = 1; i < nworst; i++) if (runs[worst[i].run].score < runs[worst[m].run].score) m = i;
         if (runs[worst[m].run].score < r->score) { slot = m; free(worst[m].tp); } }
  if (slot < 0) return;
  worst[slot].run = ri; worst[slot].n = trN; worst[slot].tp = malloc(sizeof(TP) * trN); memcpy(worst[slot].tp, trBuf, sizeof(TP) * trN);
}

#ifdef COL_DEBUG
extern int colDebug;
#endif
static int dbgF = -1;
static FILE *evf; static int quiet = 0, vrun = -1, vf0 = 0, vf1 = 0;
static int curReach;
static const char *MODEN[3] = {"road", "wild", "ram"};
static void runOne(int pt, int mode, int seed, float secs, float x, float y, float z, float h) {
  Run *R = &runs[nruns]; memset(R, 0, sizeof *R); R->reach = curReach;
  R->pt = pt; R->mode = mode; R->seed = seed; R->sx = x; R->sz = z; R->sh = h;
  rng = 0x9e3779b9u ^ ((uint32_t)pt * 7919u + (uint32_t)mode * 104729u + (uint32_t)seed * 1299709u); if (!rng) rng = 1;
  Car c; carInit(&c, 0, &W, x, y, z, h);
  Bot b; memset(&b, 0, sizeof b); b.mode = mode; b.lastX = c.x; b.lastZ = c.z;
  if (mode == 0) { b.cur = nearestRoad(c.x, c.z, c.h, 60.f); if (b.cur < 0) b.cur = 0; b.nxt = pickNext(b.cur); }
  int nfr = (int)(secs * FPS);
  static float wx[WIN], wz[WIN]; static int8_t wcmd[WIN], whead[WIN]; int wn = 0, wpos = 0;
  float penRun = 0; int penFlag = 0; float t = 0; float airRun = 0;
  trN = 0;
  for (int f = 0; f < nfr; f++) {
    CarInput in; int cmd = botStep(&b, &c, &in, t); if (cmd) b.lastCmd = cmd;
    // время кадра: чаще 1/60, иногда пропуск кадра или рывок
    float u = frand(), dt = u < 0.85f ? 1.f / 60 : u < 0.95f ? 1.f / 30 : 1.f / 60 + frand() * (1.f / 20 - 1.f / 60);
    float px = c.x, pz = c.z, py = c.y, ph = c.h; int rec0 = c.recoveries, rev0 = c.reverts;
    Car c0 = c;
    double t0 = now();
#ifdef COL_DEBUG
    colDebug = (nruns == vrun && f == dbgF);
#endif
    carUpdate(&c, &W, &in, dt);
    double el = now() - t0;
    if (el > 8e-6) {   // дорогой кадр: повторяем тот же шаг с того же состояния, берём минимум (без вытеснения ОС)
      for (int k = 0; k < 5; k++) { Car cc = c0; double t1 = now(); carUpdate(&cc, &W, &in, dt); double e = now() - t1; if (e < el) el = e; }
    }
    t += dt;
    { int k = nslow < 10 ? nslow++ : 9;   // 10 самых дорогих кадров
      if (k < 9 || el > slow[9].el) { slow[k] = (Slow){el, nruns, f, c.reverts - rev0, c.recoveries != rec0, !c.grounded, dt};
        for (int j = k; j > 0 && slow[j].el > slow[j - 1].el; j--) { Slow q = slow[j]; slow[j] = slow[j - 1]; slow[j - 1] = q; } } }
    R->cpu += el; if (el > R->cpuMax) R->cpuMax = el;
    int hb = (int)(el * 4e6); if (hb > 399) hb = 399; cpuHist[hb]++;
    if (el < 1e-4) { cpuTrim += el; nTrim++; } else nOut++;
    R->frames++;
    uint8_t fl = 0;
    int rec = c.recoveries != rec0;
    if (rec) { R->recov++; fl |= F_REC; }
    if (c.reverts != rev0) { if (evf) fprintf(evf, "%d,%s,%d,%.2f,%.2f,%.2f,%d\n", nruns, MODEN[mode], f, c.x, c.z, c.y, c.revWhy); revWhyN[c.revWhy & 63] += c.reverts - rev0; if (!R->reverts) R->firstRevF = f; R->reverts += c.reverts - rev0; fl |= F_REV; }
    if (!c.grounded) { fl |= F_AIR; airRun += dt; if (airRun > R->maxAir) R->maxAir = airRun; R->airTime += dt; } else airRun = 0;
    if (c.hitSpeed > R->maxHit) R->maxHit = c.hitSpeed;
    for (int k = 0; k < c.contacts; k++) { ctypeN[c.ctype[k] & 3]++; if (c.hitSpeed > 10.f) hitTypeN[c.ctype[k] & 3]++; }
    if (c.hitSpeed > 4.f) fl |= F_HIT;
    if (!rec) {
      float dx = c.x - px, dz = c.z - pz; R->dist += sqrtf(dx * dx + dz * dz);
      // выход за забор: путь центра кузова и начала машины
      float bo = c.p.bodyOfs;
      if (colCrossFence(&W, px + sinf(ph) * bo, pz + cosf(ph) * bo, c.x + sinf(c.h) * bo, c.z + cosf(c.h) * bo, 0, 0) ||
          colCrossFence(&W, px, pz, c.x, c.z, 0, 0)) { R->exits++; fl |= F_EXIT; }
      // провал: под центром есть проходимая поверхность не выше прошлой высоты + 0.5, а машина ниже неё на 1 м
      float G;
      if (colGround(&W, c.x, c.z, py + 0.5f, -1e6f, &G, 0)) { if (c.y < G - 1.f) { R->falls++; fl |= F_FALL; } }
      else {
        int any = 0; float fx = sinf(c.h), fz = cosf(c.h);
        for (int k = 0; k < 4 && !any; k++) {
          float lon = k < 2 ? c.p.wheelF : -c.p.wheelR, lat = (k & 1) ? c.p.wheelX : -c.p.wheelX;
          any = colGround(&W, c.x + fx * lon - fz * lat, c.z + fz * lon + fx * lat, py + 0.5f, -1e6f, &G, 0);
        }
        if (!any) { R->noSurf++; fl |= F_FALL; }
      }
    }
    // проникновение после разрешения
    CarBox pb; carBox(&c, &pb); colProbeCar(&W, &pb);
    if (pb.maxDepth > R->maxPen) R->maxPen = pb.maxDepth;
    if (pb.maxDepth > 0.05f) { penRun += dt; R->penTime += dt; fl |= F_PEN; if (penRun > 0.1f && !penFlag) { R->penEv++; penFlag = 1; } }
    else { penRun = 0; penFlag = 0; }
    // застрял: 3 с команды «ехать», смещение < 0.5 м, и не упирались в стену лбом
    // лбом в стену: касание сейчас или отскок от стены в последние 0.5 с (машина v10 отскакивает и снова въезжает)
    int head = 0;
    static int headT; if (f == 0) headT = -1000;
    if (cmd) {
      float dx = sinf(c.h) * cmd, dz = cosf(c.h) * cmd;
      for (int k = 0; k < c.contacts; k++) if (c.cnx[k] * dx + c.cnz[k] * dz < -0.15f) head = 1;
      for (int k = 0; k < pb.n; k++) if (pb.nx[k] * dx + pb.nz[k] * dz < -0.15f) head = 1;
      if (c.reverts != rev0 && (c.revWhy & 48)) head = 1;   // край мира / земля выше досягаемого — тоже стена
      if (head) headT = f; else if (f - headT < FPS / 2) head = 1;
    }
    wx[wpos] = c.x; wz[wpos] = c.z; wcmd[wpos] = (int8_t)cmd; whead[wpos] = (int8_t)head; wpos = (wpos + 1) % WIN; if (wn < WIN) wn++;
    if (rec) wn = 0;
    if (wn == WIN) {
      int allCmd = 1, nh = 0; float mx = 0;
      float x0 = wx[wpos], z0 = wz[wpos];
      for (int k = 0; k < WIN; k++) {
        if (!wcmd[k]) { allCmd = 0; break; }
        nh += whead[k]; float dx = wx[k] - x0, dz = wz[k] - z0, d = dx * dx + dz * dz; if (d > mx) mx = d;
      }
      if (allCmd && mx < 0.25f) {
        if (nruns == vrun) printf("EVENT %s at frame %d (%.2f %.2f) head %d/%d maxdisp %.2f\n", nh >= WIN * 6 / 10 ? "blocked" : "stuck", f, c.x, c.z, nh, WIN, sqrtf(mx));
        if (nh >= WIN * 6 / 10) R->blocked++;
        else { R->stuck++; fl |= F_STUCK; R->stuckX = c.x; R->stuckZ = c.z; if (!R->stuckF) R->stuckF = f; }
        wn = 0;
      }
    }
    if (nruns == vrun && f >= vf0 && f <= vf1) {
      printf("f%5d cpu %8.1f t %6.2f in(%.1f %.1f %+.2f) x %8.3f z %8.3f y %7.3f g %+.3f %+.3f h %+.4f v %+6.2f vl %+5.2f vy %+5.2f gr %d wh %d pen %.3f rev %d/%d cont %d fl %02x",
             f, el * 1e6, t, in.throttle, in.brake, in.steer, c.x, c.z, c.y, c.gx, c.gz, c.h, c.v, c.vl, c.vy, c.grounded, c.wheels, pb.maxDepth, c.reverts - rev0, c.revWhy, c.contacts, fl);
      for (int k = 0; k < c.contacts; k++) printf(" (%+.2f %+.2f)", c.cnx[k], c.cnz[k]);
      printf(" | probe %d:", pb.n);
      for (int k = 0; k < pb.n; k++) printf(" t%d(%+.2f %+.2f %.3f)", pb.type[k], pb.nx[k], pb.nz[k], pb.depth[k]);
      printf("\n");
    }
    TP *tp = &trBuf[trN++]; tp->x = c.x; tp->z = c.z; tp->y = c.y; tp->v = c.v; tp->fl = fl;
  }
  cpuAll += R->cpu; updAll += R->frames; if (R->cpuMax > cpuMaxAll) cpuMaxAll = R->cpuMax;
  R->score = 1e6 * (R->falls + R->noSurf + R->exits) + 1e5 * R->penEv + 1e4 * R->stuck + 1e3 * R->recov + 30.0 * R->blocked +
             1.0 * R->reverts + 100.0 * R->maxPen + 0.1 * R->maxHit;
  if (!quiet && (R->falls || R->noSurf || R->exits || R->penEv || R->stuck || R->recov))
    printf("  run %d pt %d %s seed %d at (%.0f %.0f): falls %d nosurf %d exits %d pen>5cm %d stuck %d (%.1f %.1f f%d) blocked %d rec %d rev %d (f%d) maxpen %.3f\n",
           nruns, pt, MODEN[mode], seed, x, z, R->falls, R->noSurf, R->exits, R->penEv, R->stuck, R->stuckX, R->stuckZ, R->stuckF,
           R->blocked, R->recov, R->reverts, R->firstRevF, R->maxPen);
  keepTrace(nruns);
  nruns++;
}

int main(int argc, char **argv) {
  const char *lvl = 0, *roadp = 0, *out = "."; float secs = 60; int seeds = 2, npts = 100000, start = 0, only = -1, modes = 7;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--roads") && i + 1 < argc) roadp = argv[++i];
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
    else if (!strcmp(argv[i], "--secs") && i + 1 < argc) secs = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--seeds") && i + 1 < argc) seeds = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--trace") && i + 1 < argc) wantTrace = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--pts") && i + 1 < argc) npts = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--start") && i + 1 < argc) start = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--only") && i + 1 < argc) only = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--mode") && i + 1 < argc) { i++; modes = !strcmp(argv[i], "road") ? 1 : !strcmp(argv[i], "wild") ? 2 : !strcmp(argv[i], "ram") ? 4 : 7; }
    else if (!strcmp(argv[i], "--quiet")) quiet = 1;
    else if (!strcmp(argv[i], "--debug-frame") && i + 1 < argc) dbgF = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--verbose") && i + 3 < argc) { vrun = atoi(argv[++i]); vf0 = atoi(argv[++i]); vf1 = atoi(argv[++i]); }
    else if (argv[i][0] != '-') lvl = argv[i];
    else { fprintf(stderr, "unknown option %s\n", argv[i]); return 2; }
  }
  if (wantTrace > 64) wantTrace = 64;
  if (!lvl) { fprintf(stderr, "usage: cartest LEVEL.shr [--roads roads.bin] [--out DIR] [--secs 60] [--seeds 2] [--trace 12]\n"); return 2; }
  loadLevel(lvl);
  if (roadp) loadRoads(roadp); else modes &= 6;
  benchPoints();
  { char fn[1024]; snprintf(fn, sizeof fn, "%s/reverts.csv", out); evf = fopen(fn, "w"); if (evf) fprintf(evf, "run,mode,frame,x,z,y,why\n"); }
  trBuf = malloc(sizeof(TP) * (size_t)(secs * 1.5f * FPS + 16));
  printf("level %s: COL1 %u tri %u box %u cyl %u seg, grid %dx%d; bench points %d; roads %d\n",
         lvl, W.ntri, W.nbox, W.ncyl, W.nseg, W.W, W.H, nbp, nroad);
  int skipOut = 0, skipEmb = 0, skipNoG = 0, used = 0, nReach = 0;
  { float *hd = (float *)(file + 12); reachFill(hd[6], hd[7], hd[8]); }
  double t0 = now();
  for (int p = start; p < nbp && used < npts; p++) {
    if (only >= 0 && p != only) continue;
    float x = bpx[p], z = bpz[p], g;
    if (insideFences(x, z)) { skipOut++; continue; }
    if (!colGround(&W, x, z, bpy[p] + 2.f, -1e6f, &g, 0)) { skipNoG++; continue; }
    // курс: вдоль ближайшей дороги, иначе 0; кузов не должен стартовать в стене
    int ri = roadp ? nearestRoad(x, z, 100.f, 40.f) : -1;
    float h = ri >= 0 ? atan2f(roads[ri].bx - roads[ri].ax, roads[ri].bz - roads[ri].az) : 0.f;
    int ok = 0;
    for (int k = 0; k < 8 && !ok; k++) {
      float hh_ = h + k * (PI / 4);
      Car c; carInit(&c, 0, &W, x, g, z, hh_);
      CarBox b; carBox(&c, &b); colProbeCar(&W, &b);
      if (b.maxDepth < 0.02f && c.grounded && c.wheels >= 3 && !insideFences(b.x, b.z)) { ok = 1; h = hh_; x = c.x; z = c.z; g = c.y; }
    }
    if (!ok) { skipEmb++; continue; }
    used++; curReach = reachable(x, g, z); nReach += curReach;
    if ((modes & 1) && ri >= 0) runOne(p, 0, 0, secs * 1.5f, x, g, z, h);
    if (modes & 2) for (int s = 0; s < seeds; s++) runOne(p, 1, s, secs, x, g, z, h + s * 1.3f);
    if (nruns >= MAXRUNS - 8) break;
  }
  // таран: машина в 25 м от забора / ящика / цилиндра, газ в пол 3 с (к 30 м/с) под углами 0/45/70 градусов
  long ramHit20 = 0;
  if (modes & 4) {
    float ang[3] = {0.f, 0.785f, 1.22f};
    for (int kind = 0; kind < 3; kind++) {
      int cnt = kind == 0 ? (int)W.nseg : kind == 1 ? (int)W.nbox : (int)W.ncyl, stepK = kind == 0 ? 3 : 2;
      for (int i = 0; i < cnt; i += stepK)
        for (int a = 0; a < (kind == 0 ? 3 : 4); a++) {
          float tx, tz, nx, nz, ext = 0.f;
          if (kind == 0) {
            const ColSeg *g = &W.seg[i]; float dx = g->b[0] - g->a[0], dz = g->b[1] - g->a[1];
            if (dx * dx + dz * dz < 1.f) continue;
            tx = (g->a[0] + g->b[0]) * .5f; tz = (g->a[1] + g->b[1]) * .5f;
            float ca = cosf(ang[a]), sa = sinf(ang[a]) * ((i / 3) & 1 ? 1.f : -1.f);
            nx = g->n[0] * ca - g->n[1] * sa; nz = g->n[0] * sa + g->n[1] * ca;
          } else {
            const float *c3 = kind == 1 ? W.box[i].c : W.cyl[i].c;
            tx = c3[0]; tz = c3[2]; nx = sinf(a * 1.5708f + 0.3f); nz = cosf(a * 1.5708f + 0.3f);
            if (kind == 1) { const ColBox *B = &W.box[i]; ext = fabsf(B->ax[0]) * B->h[0] + fabsf(B->ay[0]) * B->h[1] + fabsf(B->az[0]) * B->h[2];
                             float ez = fabsf(B->ax[2]) * B->h[0] + fabsf(B->ay[2]) * B->h[1] + fabsf(B->az[2]) * B->h[2]; if (ez > ext) ext = ez;
                             if (ext > 30.f) continue; }
            else ext = W.cyl[i].r + W.cyl[i].halfLen;
          }
          float sx = tx + nx * (25.f + ext), sz = tz + nz * (25.f + ext), g;
          float gy0; if (!colGround(&W, tx + nx * (1.f + ext), tz + nz * (1.f + ext), 1e6f, -1e6f, &gy0, 0)) continue;
          if (!colGround(&W, sx, sz, gy0 + 4.f, -1e6f, &g, 0) || fabsf(g - gy0) > 4.f) continue;
          if (!reachable(sx, g, sz) || insideFences(sx, sz)) continue;
          float h = atan2f(tx - sx, tz - sz);
          Car c; carInit(&c, 0, &W, sx, g, sz, h); CarBox b; carBox(&c, &b); colProbeCar(&W, &b);
          if (b.maxDepth > 0.02f || !c.grounded || c.wheels < 3 || !reachable(c.x, c.y, c.z)) continue;
          curReach = 1; runOne(-1 - kind, 2, i * 4 + a, 3.f / 1.5f, c.x, c.y, c.z, h);
          if (runs[nruns - 1].maxHit > 20.f) ramHit20++;
          if (nruns >= MAXRUNS - 8) break;
        }
    }
  }
  double wall = now() - t0;
  if (evf) fclose(evf);
  // итог
  long falls = 0, nos = 0, exits = 0, pen = 0, stuck = 0, blocked = 0, rec = 0, rev = 0, frames = 0; float maxPen = 0, maxHit = 0; double penT = 0, dist = 0, air = 0;
  long rstuck[3] = {0, 0, 0}, rblocked[3] = {0, 0, 0}, rrec[3] = {0, 0, 0}, rrev[3] = {0, 0, 0}, rn[3] = {0, 0, 0}; double rdist[3] = {0, 0, 0};
  long qf = 0, qn = 0, qe = 0, qp = 0, qs = 0, qb = 0, qr = 0, qv = 0, qruns = 0;   // только досягаемые старты
  for (int i = 0; i < nruns; i++) {
    Run *r = &runs[i];
    falls += r->falls; nos += r->noSurf; exits += r->exits; pen += r->penEv; stuck += r->stuck; blocked += r->blocked; rec += r->recov; rev += r->reverts;
    frames += r->frames; if (r->maxPen > maxPen) maxPen = r->maxPen; if (r->maxHit > maxHit) maxHit = r->maxHit; penT += r->penTime; dist += r->dist; air += r->airTime;
    if (r->reach) { qruns++; qf += r->falls; qn += r->noSurf; qe += r->exits; qp += r->penEv; qs += r->stuck; qb += r->blocked; qr += r->recov; qv += r->reverts; }
    rstuck[r->mode] += r->stuck; rblocked[r->mode] += r->blocked; rrec[r->mode] += r->recov; rrev[r->mode] += r->reverts; rn[r->mode]++; rdist[r->mode] += r->dist;
  }
  long acc = 0; double p50 = 0, p99 = 0, p999 = 0;
  for (int i = 0; i < 400; i++) { acc += cpuHist[i]; if (!p50 && acc >= updAll * 0.5) p50 = (i + 1) * 0.25; if (!p99 && acc >= updAll * 0.99) p99 = (i + 1) * 0.25; if (!p999 && acc >= updAll * 0.999) p999 = (i + 1) * 0.25; }
  char sum[4096]; int n = 0;
  n += snprintf(sum + n, sizeof sum - n,
    "CARTEST  %s\n"
    "starts: %d used (%d reachable from spawn by a fill over walkable ground: %ld cells of 2 m), skipped: %d inside fence loops, %d embedded at every heading, %d no ground\n"
    "runs: %d (road %ld, wild %ld, ram %ld: %ld of them hit at > 20 m/s), %.0f s simulated, %ld car updates, driven %.1f km (road %.1f, wild %.1f), airborne %.0f s\n"
    "  metric                                   total   road   wild    ram  | reachable starts only (%ld runs)\n"
    "  falls through ground (y < surface - 1m)  %5ld                       | %5ld\n"
    "  no surface under car (frames)            %5ld                       | %5ld\n"
    "  world exits (fence crossed)              %5ld                       | %5ld\n"
    "  penetration > 5 cm for > 0.1 s           %5ld                       | %5ld   (max depth %.3f m, time > 5 cm %.2f s)\n"
    "  stuck (3 s moving cmd, < 0.5 m, no wall) %5ld  %5ld  %5ld  %5ld  | %5ld\n"
    "  blocked (3 s, pushing into a wall)       %5ld  %5ld  %5ld  %5ld  | %5ld\n"
    "  recoveries                               %5ld  %5ld  %5ld  %5ld  | %5ld\n"
    "  reverted substeps                        %5ld  %5ld  %5ld  %5ld  | %5ld\n"
    "    by reason: no fit %ld, behind fence %ld, path through fence %ld, void edge %ld, ground above reach %ld\n"
    "  hardest hit %.1f m/s; contact frames by type: steep tri %ld, box %ld, cyl %ld, fence %ld (hits > 10 m/s: %ld %ld %ld %ld)\n"
    "cpu per car update (Mac, frames over 8 us re-timed 5x from the same state, min taken): avg %.2f us (%ld still > 100 us; avg without them %.2f us), p50 %.2f, p99 %.2f, p99.9 %.2f, max %.1f us\n"
    "Mac timings do not predict PSP performance; measure the same workload on hardware.\n"
    "wall time %.1f s\n",
    lvl, used, nReach, reachN, skipOut, skipEmb, skipNoG, nruns, rn[0], rn[1], rn[2], ramHit20, frames / (double)FPS, updAll, dist / 1000, rdist[0] / 1000, rdist[1] / 1000, air,
    qruns, falls, qf, nos, qn, exits, qe, pen, qp, maxPen, penT, stuck, rstuck[0], rstuck[1], rstuck[2], qs, blocked, rblocked[0], rblocked[1], rblocked[2], qb, rec, rrec[0], rrec[1], rrec[2], qr, rev, rrev[0], rrev[1], rrev[2], qv, revWhyN[1] + revWhyN[3], revWhyN[2], revWhyN[4] + revWhyN[8], revWhyN[16], revWhyN[32], maxHit, ctypeN[0], ctypeN[1], ctypeN[2], ctypeN[3], hitTypeN[0], hitTypeN[1], hitTypeN[2], hitTypeN[3],
    cpuAll / updAll * 1e6, nOut, cpuTrim / nTrim * 1e6, p50, p99, p999, cpuMaxAll * 1e6, wall);
  fputs(sum, stdout);
  if (!quiet || 1) { printf("slowest updates (us: run frame dt substeps reverts recovery airborne):"); for (int i = 0; i < nslow; i++) printf(" [%.1f: r%d f%d dt %.3f sub %d rev %d rec %d air %d]", slow[i].el * 1e6, slow[i].run, slow[i].frame, slow[i].dt, (int)(slow[i].dt * 120.f + .5f), slow[i].rev, slow[i].rec, slow[i].air); printf("\n"); }
  char fn[1024];
  snprintf(fn, sizeof fn, "%s/summary.txt", out); FILE *f = fopen(fn, "w"); if (f) { fputs(sum, f); fclose(f); }
  snprintf(fn, sizeof fn, "%s/runs.csv", out); f = fopen(fn, "w");
  if (f) {
    fprintf(f, "run,pt,mode,seed,reach,x,z,h,falls,nosurf,exits,pen_events,stuck,blocked,recoveries,reverts,max_pen,pen_time,max_hit,dist,air,cpu_avg_us,cpu_max_us,stuck_x,stuck_z,score\n");
    for (int i = 0; i < nruns; i++) { Run *r = &runs[i];
      fprintf(f, "%d,%d,%s,%d,%d,%.1f,%.1f,%.2f,%d,%d,%d,%d,%d,%d,%d,%d,%.4f,%.2f,%.1f,%.0f,%.1f,%.2f,%.1f,%.1f,%.1f,%.0f\n", i, r->pt, MODEN[r->mode], r->seed, r->reach,
              r->sx, r->sz, r->sh, r->falls, r->noSurf, r->exits, r->penEv, r->stuck, r->blocked, r->recov, r->reverts, r->maxPen, r->penTime, r->maxHit, r->dist, r->airTime,
              r->cpu / r->frames * 1e6, r->cpuMax * 1e6, r->stuckX, r->stuckZ, r->score); }
    fclose(f);
  }
  snprintf(fn, sizeof fn, "%s/traces.bin", out); f = fopen(fn, "wb");
  if (f) {
    // заголовок: "TRC1", число трасс; на трассу: run, pt, mode, seed, n, score(float), затем n x (x z y v fl)
    fwrite("TRC1", 1, 4, f); int32_t k = nworst; fwrite(&k, 4, 1, f);
    for (int i = 0; i < nworst; i++) {
      Run *r = &runs[worst[i].run]; int32_t h5[5] = {worst[i].run, r->pt, r->mode, r->seed, worst[i].n}; float sc = (float)r->score;
      fwrite(h5, 4, 5, f); fwrite(&sc, 4, 1, f);
      for (int j = 0; j < worst[i].n; j++) { TP *p = &worst[i].tp[j]; float v4[4] = {p->x, p->z, p->y, p->v}; fwrite(v4, 4, 4, f); fwrite(&p->fl, 1, 1, f); }
    }
    fclose(f);
  }
  return (falls || nos || exits || pen) ? 1 : 0;
}
