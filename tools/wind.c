// wind.c: обход треугольников города под отсечение задних граней (шаг 3.4 аудита), SHR7 без индексов (флаг 16).
//
// Меши уровня не несут нормалей, а оригинал рисует всё двусторонним — обход у художников «какой получился»
// (tests/gebench: 31% видимых пикселей худшего вида — с чужим обходом). Поэтому обход решает голосование видами:
// из точек глаза по всему уровню (сетка STEP м по карте высот, каждый проходимый слой, высоты глаза EYEH) программно
// рисуется куб 6 граней с глубиной; в каждом пикселе запоминается треугольник-победитель и видна ли его лицевая
// сторона. Лицевая = CCW на экране (y вверх), как sceGuFrontFace(GU_CCW) в движке: dot((b-a)x(c-a), глаз - a) > 0.
// Непрозрачное и альфа-тест пишут глубину; полупрозрачное (флаг 2) проверяется по ней и голосует отдельно.
// Ближняя версия куска рисуется ближе 50 м (расстояние до ящика, как в движке), дальняя — дальше; до 115 м.
// Итог по каждому куску города:
//   * треугольник, который чаще видят с изнанки, разворачивается (меняются местами вершины 1 и 2);
//   * если после этого у куска остаётся заметная доля пикселей «с изнанки» (заборы, листва, вывески видны с обеих
//     сторон) или кусок не виден ни из одного глаза — флаг 8 «двусторонний»: движок рисует его без отсечения.
// Файл правится на месте (флаги в таблице кусков + порядок вершин в блобах), PVS и остальное не трогается.
//
// Сборка: cc -O3 -o tools/wind tools/wind.c -lm -lpthread
// Запуск: tools/wind LEVEL.shr [--step 10] [--res 96] [--rel 0.002] [--abs 24] [--tri 2] [--trel 0.02] [--inside 0.25] [--threads N] [--dry]
//   --tri/--trel: кусок двусторонний, если хоть один его треугольник виден с обеих сторон (>= 2 px и >= 2% его пикселей)
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include <unistd.h>

typedef struct { float bb[6]; int32_t tex; uint32_t flags, nv, ni, owner; float ox, oy, oz, sc; uint32_t off, nf, cell, pad[2]; } Rec;
typedef struct { float bb[6]; uint32_t first, n, owner, off, size, pad; } CellRec;
_Static_assert(sizeof(Rec) == 80, "Rec 80");
_Static_assert(sizeof(CellRec) == 48, "CellRec 48");

enum { F_ALPHA = 1, F_BLEND = 2, F_SKY = 4, F_DOUBLE = 8, F_NOIDX = 16, F_V12 = 32, F_LSIDE = 512, F_NEAR = 2048, F_FARP = 1 << 25 };
// F_LSIDE (tools/psp_export.py mark_layers, правки Роба 37/43): слой со стороной — обход уже лицом от подложки, движок рисует
// его с отсечением изнанки; голосование его не разворачивает и флаг 8 не ставит (с изнанки его закрывает подложка)
static int OFFS = 0;   // --offset N: сдвиг сетки глаз на N клеток карты высот (проверка на других точках)
static float STEP = 10.f, EYEH[4] = {1.0f, 2.4f, 3.5f, 6.5f}, NEAR = 0.7f, DRAW = 115.f, LOD = 50.f, REL = 0.002f;
static int CHECK;   // --check: только проверка текущих флагов/обхода файла (ничего не меняет): пиксели с изнанки у отсекаемых кусков, отдельно земля
static int TRIK = 2; static float TREL = 0.02f;   // --tri K: кусок двусторонний, если хоть один треугольник виден с обеих сторон (>= K px и >= TREL его пикселей)
static int NEYEH = 4, RES = 96, ABS_ = 24, NTH = 8, DRY = 0;

static float FARD = 60.f; static int FARONLY; static uint8_t *ISFAR;   // правка 508: --far-d D --far-only: голосуют только дальние версии кусков F_FARP (дальше D), ближние не трогаются
typedef struct { int ok, blend, ntri[2]; uint32_t base[2]; float bb[6]; float *v[2]; uint8_t *blob[2]; int vs, nearAll, farp; } Piece;
static Piece *P; static int NP; static uint32_t NTRI;
static const int16_t *HM; static int HW, HH; static float HOX, HOZ, HCELL;
static float *EYES; static int NEYES; static volatile int nextEye;
static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;
static uint32_t *CF, *CB;   // голоса: пикселей с лицевой / с изнанки, на треугольник
static uint8_t *MAJ; static int PASS;   // проход 1: голосуют все глаза -> MAJ[t] = 1, если чаще видят с изнанки;
                                        // проход 2: глаз «внутри геометрии» (много пикселей против MAJ) не голосует

static float boxD2(const float *b, const float *e) {
  float d = 0;
  for (int a = 0; a < 3; a++) { float t = b[a] - e[a] > 0 ? b[a] - e[a] : (e[a] - b[a + 3] > 0 ? e[a] - b[a + 3] : 0); d += t * t; }
  return d;
}

typedef struct { float *z, *zb; uint32_t *id, *idb; uint32_t *cf, *cb; uint32_t *hit; int nhit; long long skipped; } Ctx;
static float INSIDE = 0.25f;   // глаз, у которого с изнанки больше этой доли непрозрачных пикселей, — внутри геометрии, не голосует
static const int WA[6] = {0, 0, 1, 1, 2, 2}, UA[6] = {2, 2, 0, 0, 0, 0}, VA[6] = {1, 1, 2, 2, 1, 1};

// один треугольник на грань куба: отсечение по ближней плоскости w >= NEAR, растр по центрам пикселей, z = 1/w
static void tri(Ctx *c, int f, const float *A, const float *B, const float *C, uint32_t id, int blend) {
  const float *T[3] = {A, B, C}; float q[3][3], poly[5][3]; int np = 0;
  for (int k = 0; k < 3; k++) { q[k][0] = T[k][UA[f]]; q[k][1] = T[k][VA[f]]; q[k][2] = (f & 1) ? -T[k][WA[f]] : T[k][WA[f]]; }
  if (q[0][2] < NEAR && q[1][2] < NEAR && q[2][2] < NEAR) return;
  for (int k = 0; k < 3; k++) {
    const float *a = q[k], *b = q[(k + 1) % 3]; int ia = a[2] >= NEAR, ib = b[2] >= NEAR;
    if (ia) { memcpy(poly[np], a, 12); np++; }
    if (ia != ib) { float t = (NEAR - a[2]) / (b[2] - a[2]); for (int j = 0; j < 3; j++) poly[np][j] = a[j] + (b[j] - a[j]) * t; np++; }
  }
  float s[5][3]; int any = 0;
  for (int k = 0; k < np; k++) {
    float iw = 1.f / poly[k][2]; s[k][0] = (poly[k][0] * iw + 1.f) * .5f * RES; s[k][1] = (poly[k][1] * iw + 1.f) * .5f * RES; s[k][2] = iw;
    if (s[k][0] > -1 && s[k][0] < RES + 1 && s[k][1] > -1 && s[k][1] < RES + 1) any = 1;
  }
  (void)any;
  float *zb = blend ? c->zb : c->z; uint32_t *ib = blend ? c->idb : c->id;
  for (int k = 1; k + 1 < np; k++) {
    double x0 = s[0][0], y0 = s[0][1], x1 = s[k][0], y1 = s[k][1], x2 = s[k + 1][0], y2 = s[k + 1][1];
    double det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (fabs(det) < 1e-12) continue;
    double mnx = fmin(x0, fmin(x1, x2)), mxx = fmax(x0, fmax(x1, x2)), mny = fmin(y0, fmin(y1, y2)), mxy = fmax(y0, fmax(y1, y2));
    int px0 = (int)fmax(0, ceil(mnx - .5)), px1 = (int)fmin(RES - 1, floor(mxx - .5));
    int py0 = (int)fmax(0, ceil(mny - .5)), py1 = (int)fmin(RES - 1, floor(mxy - .5));
    if (px0 > px1 || py0 > py1) continue;
    double zA = ((s[k][2] - s[0][2]) * (y2 - y0) - (s[k + 1][2] - s[0][2]) * (y1 - y0)) / det;
    double zB = ((x1 - x0) * (s[k + 1][2] - s[0][2]) - (x2 - x0) * (s[k][2] - s[0][2])) / det;
    for (int py = py0; py <= py1; py++) {
      double y = py + .5;
      for (int px = px0; px <= px1; px++) {
        double x = px + .5;
        double w0 = (x1 - x) * (y2 - y) - (x2 - x) * (y1 - y), w1 = (x2 - x) * (y0 - y) - (x0 - x) * (y2 - y), w2 = (x0 - x) * (y1 - y) - (x1 - x) * (y0 - y);
        if (det > 0 ? (w0 < 0 || w1 < 0 || w2 < 0) : (w0 > 0 || w1 > 0 || w2 > 0)) continue;
        float z = (float)(s[0][2] + zA * (x - x0) + zB * (y - y0)); int o = py * RES + px;
        if (z <= c->z[o]) continue;                    // за непрозрачным
        if (blend && z <= zb[o]) continue;
        zb[o] = z; ib[o] = id;
      }
    }
  }
}

static void eye(Ctx *c, const float *e) {
  c->nhit = 0; long nop = 0, nback = 0;
  for (int f = 0; f < 6; f++) {
    for (int i = 0; i < RES * RES; i++) { c->z[i] = 0; c->zb[i] = 0; c->id[i] = c->idb[i] = 0xFFFFFFFFu; }
    for (int pass = 0; pass < 2; pass++)
      for (int k = 0; k < NP; k++) {
        Piece *p = &P[k]; if (!p->ok || p->blend != pass) continue;
        float d2 = boxD2(p->bb, e); if (d2 > DRAW * DRAW) continue;
        // флаг 2048 — ближняя на любой дальности; правка 508 (--far-only): у куска с F_FARP дальше FARD — дальняя версия без нарезки, как у движка (far_plain)
        int fars[2], nver = 1;
        if (!p->nearAll) fars[0] = d2 > LOD * LOD;
        else fars[0] = FARONLY && p->farp && d2 > FARD * FARD;
        for (int ver = 0; ver < nver; ver++) {
        int far = fars[ver]; const float *v = p->v[far]; int n = p->ntri[far];
        // грубо: ящик куска целиком за гранью?
        {
          float lo[3], hi[3]; for (int a = 0; a < 3; a++) { lo[a] = p->bb[a] - e[a]; hi[a] = p->bb[a + 3] - e[a]; }
          float wmax = (f & 1) ? -lo[WA[f]] : hi[WA[f]]; if (wmax < NEAR) continue;
        }
        for (int t = 0; t < n; t++) {
          const float *a = v + 9 * t; float A[3], B[3], C[3];
          for (int j = 0; j < 3; j++) { A[j] = a[j] - e[j]; B[j] = a[3 + j] - e[j]; C[j] = a[6 + j] - e[j]; }
          float ux = B[0] - A[0], uy = B[1] - A[1], uz = B[2] - A[2], vx = C[0] - A[0], vy = C[1] - A[1], vz = C[2] - A[2];
          float nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
          float sd = -(nx * A[0] + ny * A[1] + nz * A[2]);   // dot(n, глаз - a), глаз = 0
          if (sd == 0.f) continue;
          tri(c, f, A, B, C, (p->base[far] + t) | (sd > 0 ? 0x80000000u : 0), pass);
        }
        }
      }
    for (int i = 0; i < RES * RES; i++)
      for (int b = 0; b < 2; b++) {
        uint32_t id = b ? c->idb[i] : c->id[i]; if (id == 0xFFFFFFFFu) continue;
        c->hit[c->nhit++] = id;
        if (!b) { nop++; if (PASS == 2 && (!FARONLY || ISFAR[id & 0x7FFFFFFFu]) && (int)!(id & 0x80000000u) != (int)MAJ[id & 0x7FFFFFFFu]) nback++; }
      }
  }
  if (nop && nback > INSIDE * nop) { c->skipped++; return; }
  for (int i = 0; i < c->nhit; i++) { uint32_t id = c->hit[i]; if (FARONLY && !ISFAR[id & 0x7FFFFFFFu]) continue; if (id & 0x80000000u) c->cf[id & 0x7FFFFFFFu]++; else c->cb[id]++; }
}

static void *worker(void *arg) {
  Ctx *c = arg;
  for (;;) {
    pthread_mutex_lock(&mtx); int i = nextEye++; pthread_mutex_unlock(&mtx);
    if (i >= NEYES) break;
    eye(c, EYES + 3 * i);
    if (i % 2000 == 0) { fprintf(stderr, "  глаз %d / %d\n", i, NEYES); }
  }
  return 0;
}

int main(int argc, char **argv) {
  const char *in = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--far-d") && i + 1 < argc) FARD = (float)atof(argv[++i]);   // правка 508
    else if (!strcmp(argv[i], "--far-only")) FARONLY = 1;
    else if (!strcmp(argv[i], "--step") && i + 1 < argc) STEP = atof(argv[++i]);
    else if (!strcmp(argv[i], "--res") && i + 1 < argc) RES = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--rel") && i + 1 < argc) REL = atof(argv[++i]);
    else if (!strcmp(argv[i], "--abs") && i + 1 < argc) ABS_ = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--threads") && i + 1 < argc) NTH = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--dry")) DRY = 1;
    else if (!strcmp(argv[i], "--tri") && i + 1 < argc) TRIK = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--heights") && i + 1 < argc) {   // высоты глаза через запятую (до 4), по умолчанию 1.5,3.5
      NEYEH = 0; for (char *t = strtok(argv[++i], ","); t && NEYEH < 4; t = strtok(0, ",")) EYEH[NEYEH++] = atof(t); }
    else if (!strcmp(argv[i], "--check")) CHECK = 1;
    else if (!strcmp(argv[i], "--offset") && i + 1 < argc) OFFS = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--trel") && i + 1 < argc) TREL = atof(argv[++i]);
    else if (!strcmp(argv[i], "--inside") && i + 1 < argc) INSIDE = atof(argv[++i]);
    else in = argv[i];
  }
  if (!in) { fprintf(stderr, "usage: wind LEVEL.shr [--step 10] [--res 96] [--rel 0.002] [--abs 24] [--threads N] [--dry]\n"); return 2; }
  long nc = sysconf(_SC_NPROCESSORS_ONLN); if (nc > 0 && NTH == 8) NTH = (int)nc; if (NTH < 1) NTH = 1; if (NTH > 64) NTH = 64;
  FILE *f = fopen(in, "rb"); if (!f) { perror(in); return 1; }
  fseek(f, 0, SEEK_END); size_t size = ftell(f); fseek(f, 0, SEEK_SET);
  uint8_t *file = malloc(size); if (!file || fread(file, 1, size, f) != size) { fprintf(stderr, "read failed\n"); return 1; }
  fclose(f);
  if (size < 104 || memcmp(file, "SHR7", 4)) { fprintf(stderr, "%s: not SHR7\n", in); return 1; }
  uint32_t npc, ncell, tableOff, cellOff; float hd[14];
  memcpy(&npc, file + 8, 4); memcpy(&tableOff, file + 76, 4); memcpy(&ncell, file + 80, 4); memcpy(&cellOff, file + 84, 4);
  memcpy(hd, file + 12, sizeof hd); HOX = hd[11]; HOZ = hd[12]; HCELL = hd[13];
  memcpy(&HW, file + 68, 4); memcpy(&HH, file + 72, 4); HM = (const int16_t *)(file + 104);
  Rec *recs = (Rec *)(file + tableOff); const CellRec *cells = (const CellRec *)(file + cellOff);
  NP = (int)npc; P = calloc(NP, sizeof(Piece));
  int nskip = 0;
  for (int i = 0; i < NP; i++) {
    Rec *r = &recs[i]; Piece *p = &P[i];
    if (r->owner != 0) continue;
    if (!(r->flags & F_NOIDX)) { nskip++; continue; }
    p->ok = 1; p->blend = (r->flags & F_BLEND) != 0; p->vs = (r->flags & F_V12) ? 12 : 16;
    p->farp = (r->flags & F_FARP) != 0 && r->nf > 0;
    p->nearAll = (r->flags & F_NEAR) != 0;   // правки 224/237/251: кусок и вдали — ближней версией (viewer/main.c drawPiece)
    memcpy(p->bb, r->bb, sizeof p->bb);
    p->ntri[0] = r->ni / 3; p->ntri[1] = r->nf / 3;
    uint8_t *b = file + cells[r->cell].off + r->off;
    for (int ver = 0; ver < 2; ver++) {
      int n = p->ntri[ver]; p->blob[ver] = b + (ver ? (size_t)r->ni * p->vs : 0);
      p->v[ver] = malloc(sizeof(float) * 9 * (n ? n : 1)); p->base[ver] = NTRI; NTRI += n;
      for (int k = 0; k < 3 * n; k++) {
        const int16_t *q = (const int16_t *)(p->blob[ver] + (size_t)k * p->vs + (p->vs == 12 ? 6 : 8));
        p->v[ver][3 * k] = r->ox + q[0] * (r->sc / 32768.f);
        p->v[ver][3 * k + 1] = r->oy + q[1] * (r->sc / 32768.f);
        p->v[ver][3 * k + 2] = r->oz + q[2] * (r->sc / 32768.f);
      }
    }
  }
  if (nskip) fprintf(stderr, "%d кусков города с индексами — пропущены (нужен экспорт без индексов)\n", nskip);
  // глаза: сетка STEP м, каждый проходимый слой карты высот, высоты EYEH над ним
  int st = (int)(STEP / HCELL + .5f); if (st < 1) st = 1;
  int cap = 1024; EYES = malloc(sizeof(float) * 3 * cap);
  for (int gz = st / 2 + OFFS; gz < HH; gz += st)
    for (int gx = st / 2 + OFFS; gx < HW; gx += st)
      for (int l = 0; l < 4; l++) {
        int16_t h = HM[((size_t)gz * HW + gx) * 4 + l]; if (h == -32768) continue;
        for (int k = 0; k < NEYEH; k++) {
          if (NEYES == cap) { cap *= 2; EYES = realloc(EYES, sizeof(float) * 3 * cap); }
          EYES[3 * NEYES] = HOX + (gx + .5f) * HCELL; EYES[3 * NEYES + 1] = h * .01f + EYEH[k]; EYES[3 * NEYES + 2] = HOZ + (gz + .5f) * HCELL; NEYES++;
        }
      }
  fprintf(stderr, "%s: %d кусков, треуг. (ближних+дальних) %u, глаз %d (шаг %.0f м, высоты от %.1f до %.1f), куб %dx%d, потоков %d\n",
          in, NP, NTRI, NEYES, STEP, EYEH[0], EYEH[NEYEH - 1], RES, RES, NTH);
  pthread_t th[64]; Ctx ctx[64];
  for (int i = 0; i < NTH; i++) {
    Ctx *c = &ctx[i]; c->z = malloc(4 * RES * RES); c->zb = malloc(4 * RES * RES); c->id = malloc(4 * RES * RES); c->idb = malloc(4 * RES * RES);
    c->cf = calloc(NTRI + 1, 4); c->cb = calloc(NTRI + 1, 4); c->hit = malloc(4 * 12 * RES * RES);
  }
  CF = calloc(NTRI + 1, 4); CB = calloc(NTRI + 1, 4); MAJ = calloc(NTRI + 1, 1); ISFAR = calloc(NTRI + 1, 1);
  for (int i = 0; i < NP; i++) if (P[i].ok && P[i].farp) for (int t = 0; t < P[i].ntri[1]; t++) ISFAR[P[i].base[1] + t] = 1;
  long long skipped = 0;
  for (PASS = 1; PASS <= 2; PASS++) {
    nextEye = 0; skipped = 0; memset(CF, 0, 4 * (NTRI + 1)); memset(CB, 0, 4 * (NTRI + 1));
    for (int i = 0; i < NTH; i++) {
      Ctx *c = &ctx[i]; memset(c->cf, 0, 4 * (NTRI + 1)); memset(c->cb, 0, 4 * (NTRI + 1)); c->skipped = 0;
      pthread_create(&th[i], 0, worker, c);
    }
    for (int i = 0; i < NTH; i++) {
      pthread_join(th[i], 0); skipped += ctx[i].skipped;
      for (uint32_t t = 0; t < NTRI; t++) { CF[t] += ctx[i].cf[t]; CB[t] += ctx[i].cb[t]; }
    }
    for (uint32_t t = 0; t < NTRI; t++) MAJ[t] = CB[t] > CF[t];
  }
  fprintf(stderr, "глаз внутри геометрии (против большинства > %.0f%% непрозрачных пикселей), не голосуют: %lld из %d\n", INSIDE * 100, skipped, NEYES);
  if (CHECK) {
    long long all = 0, bad = 0, badG = 0, allG = 0; int npb = 0;
    for (int i = 0; i < NP; i++) {
      Piece *p = &P[i]; if (!p->ok) continue; int cull = !(recs[i].flags & F_DOUBLE); long long pb = 0;
      for (int ver = 0; ver < 2; ver++) for (int t = 0; t < p->ntri[ver]; t++) {
        uint32_t g = p->base[ver] + t; const float *v = p->v[ver] + 9 * t;
        float ux = v[3] - v[0], uy = v[4] - v[1], uz = v[5] - v[2], wx = v[6] - v[0], wy = v[7] - v[1], wz = v[8] - v[2];
        float nx = uy * wz - uz * wy, ny = uz * wx - ux * wz, nz = ux * wy - uy * wx, ln = sqrtf(nx * nx + ny * ny + nz * nz) + 1e-12f;
        int ground = fabsf(ny) / ln > .55f;
        all += CF[g] + CB[g]; if (ground) allG += CF[g] + CB[g];
        if (cull) { bad += CB[g]; pb += CB[g]; if (ground) badG += CB[g]; }
      }
      if (pb) npb++;
    }
    fprintf(stderr, "ПРОВЕРКА (высоты глаза %.1f..%.1f): видимых px %lld, с изнанки у отсекаемых %lld (%.4f%%) в %d кусках; "
            "земля/дорога: %lld из %lld (%.4f%%)\n", EYEH[0], EYEH[NEYEH - 1], all, bad, 100.0 * bad / (all ? all : 1), npb, badG, allG, 100.0 * badG / (allG ? allG : 1));
    return 0;
  }
  if (DRY) {   // сводка по порогам: доля треуг. в двусторонних кусках и остаток пикселей с изнанки в отсекаемых
    static const float rels[] = {0.002f, 0.005f, 0.01f, 0.02f, 0.05f}; static const int abss[] = {24, 100, 400, 2000};
    for (int ri = 0; ri < 5; ri++) for (int ai = 0; ai < 4; ai++) {
      long long allT = 0, dblT = 0, pixAll = 0, pixBad = 0;
      for (int i = 0; i < NP; i++) {
        Piece *p = &P[i]; if (!p->ok) continue; long long tot = 0, minor = 0; int ntr = p->ntri[0] + p->ntri[1];
        for (int ver = 0; ver < 2; ver++) for (int t = 0; t < p->ntri[ver]; t++) { uint32_t g = p->base[ver] + t, a = CF[g], b = CB[g]; tot += a + b; minor += a < b ? a : b; }
        allT += ntr; pixAll += tot;
        if (tot == 0 || (minor > abss[ai] && minor > rels[ri] * tot)) dblT += ntr; else pixBad += minor;
      }
      fprintf(stderr, "  rel %.3f abs %5d: двусторонних треуг. %5.1f%%, остаток %.4f%%\n", rels[ri], abss[ai], 100.0 * dblT / allT, 100.0 * pixBad / pixAll);
    }
  }
  // решение по кускам
  long long flipT = 0, allT = 0, dblT = 0, unseenT = 0, pixAll = 0, pixBad = 0, pixDbl = 0; int nflipP = 0, ndbl = 0, nunseen = 0, ncity = 0;
  for (int i = 0; i < NP; i++) {
    Piece *p = &P[i]; if (!p->ok) continue; ncity++;
    if (recs[i].flags & F_LSIDE) continue;   // слой со стороной: обход задан экспортом
    if (FARONLY && !p->farp) continue;
    long long tot = 0, minor = 0; int flips = 0, ntr = p->ntri[0] + p->ntri[1], two = 0;
    for (int ver = FARONLY ? 1 : 0; ver < 2; ver++)
      for (int t = 0; t < p->ntri[ver]; t++) {
        uint32_t g = p->base[ver] + t, a = CF[g], b = CB[g];
        tot += a + b; minor += a < b ? a : b;
        if (TRIK && (a < b ? a : b) >= (uint32_t)TRIK && (a < b ? a : b) >= TREL * (a + b)) two = 1;
        if (b > a) {                                   // чаще видят с изнанки — развернуть
          flips++;
          uint8_t *v1 = p->blob[ver] + (size_t)(3 * t + 1) * p->vs, *v2 = v1 + p->vs, tmp[16];
          if (!DRY) { memcpy(tmp, v1, p->vs); memcpy(v1, v2, p->vs); memcpy(v2, tmp, p->vs); }
        }
      }
    allT += ntr; flipT += flips; if (flips) nflipP++; pixAll += tot;
    int dbl = tot == 0 || two || (minor > ABS_ && minor > REL * tot);
    if (tot == 0) { nunseen++; unseenT += ntr; }
    if (FARONLY) { allT += 0; continue; }   // правка 508: дальняя версия только переворачивается по голосам; двусторонность куска решена ближней версией
    if (dbl) { ndbl++; dblT += ntr; pixDbl += minor; if (!DRY) recs[i].flags |= F_DOUBLE; }
    else pixBad += minor;
  }
  fprintf(stderr, "куски города %d, треуг. %lld: развёрнуто треуг. %lld (%.1f%%) в %d кусках; двусторонних кусков %d (%.1f%% треуг.), "
          "из них не видно ни из одного глаза %d (%lld треуг.)\n",
          ncity, allT, flipT, 100.0 * flipT / (allT ? allT : 1), nflipP, ndbl, 100.0 * dblT / (allT ? allT : 1), nunseen, unseenT);
  fprintf(stderr, "видимых пикселей всего %lld: с изнанки в двусторонних %lld (%.3f%%), остаток в отсекаемых %lld (%.4f%%) — это возможные дыры\n",
          pixAll, pixDbl, 100.0 * pixDbl / (pixAll ? pixAll : 1), pixBad, 100.0 * pixBad / (pixAll ? pixAll : 1));
  if (DRY) return 0;
  char tmpn[4096]; snprintf(tmpn, sizeof tmpn, "%s.wind_tmp", in);
  f = fopen(tmpn, "wb"); if (!f || fwrite(file, 1, size, f) != size) { fprintf(stderr, "write failed\n"); return 1; }
  fclose(f); if (rename(tmpn, in)) { perror("rename"); return 1; }
  fprintf(stderr, "записано %s\n", in);
  return 0;
}
