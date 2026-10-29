// scout.c — бот-репортёр (№871, Роб 23.10: «бот, который снимает пейзажи и понимает, где нужна прорисовка вдаль, а где узко»).
// Только Мак, CPU, без ИИ. Вход — выгрузка tools/scout/dump.py (SCT1). Для каждой точки земли × высота глаза (пешком 2,0 м, из машины 3,2 м)
// × 8 направлений: кадр глубины 128×72 (угол обзора как в игре), доли экрана по дальности и цена кадра (треугольники, куски) при пороге
// крупной версии FP ∈ {60, 90, 140} м и дальности D ∈ {150, 200, 250} м. Выход — CSV, одна строка на ракурс.
//   cc -O2 -o build/scout/scout tools/scout/scout.c -lm -lpthread && build/scout/scout IN.bin OUT.csv [потоков]
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 128
#define H 72
#define FOVY_DEG 45.f
#define ZNEAR .5f
#define DMAX 250.f
#define GRID 20.f
#define NDIR 8
static const float EYEH[2] = {2.0f, 3.2f};
static const float FPS_[3] = {60.f, 90.f, 140.f}, DD_[3] = {150.f, 200.f, 250.f};
static const float BIN[6] = {40.f, 90.f, 140.f, 200.f, 250.f, 1e9f};

typedef struct { float c[4]; int32_t n[3]; } Pc;
static uint32_t ntri, npc, npt; static float *tri; static int32_t *tpc; static Pc *pc; static float *pt;
static float gx0, gz0; static int gw, gh; static uint32_t *cellStart, *cellIdx;   // треугольники по сетке GRID м
static uint32_t *pcellStart, *pcellIdx;   // куски по той же сетке
static FILE *outf; static pthread_mutex_t mx = PTHREAD_MUTEX_INITIALIZER; static int nthreads = 8;

static int gcell(float x, float z, int *cx, int *cz) { *cx = (int)floorf((x - gx0) / GRID); *cz = (int)floorf((z - gz0) / GRID); return *cx >= 0 && *cz >= 0 && *cx < gw && *cz < gh; }
static void buildGrid(void) {
  float mnx = 1e30f, mnz = 1e30f, mxx = -1e30f, mxz = -1e30f;
  for (uint32_t i = 0; i < ntri * 3; i++) { float x = tri[i * 3], z = tri[i * 3 + 2]; if (x < mnx) mnx = x; if (x > mxx) mxx = x; if (z < mnz) mnz = z; if (z > mxz) mxz = z; }
  gx0 = mnx - 1.f; gz0 = mnz - 1.f; gw = (int)((mxx - gx0) / GRID) + 2; gh = (int)((mxz - gz0) / GRID) + 2;
  uint32_t nc = (uint32_t)(gw * gh); cellStart = calloc(nc + 1, 4); cellIdx = malloc(ntri * 4);
  uint32_t *cc = calloc(nc, 4);
  for (int pass = 0; pass < 2; pass++) {
    if (pass) { uint32_t s = 0; for (uint32_t c = 0; c < nc; c++) { cellStart[c] = s; s += cc[c]; cc[c] = 0; } cellStart[nc] = s; }
    for (uint32_t i = 0; i < ntri; i++) { const float *t = tri + i * 9; int cx, cz; gcell((t[0] + t[3] + t[6]) / 3, (t[2] + t[5] + t[8]) / 3, &cx, &cz);
      if (cx < 0) cx = 0; if (cz < 0) cz = 0; if (cx >= gw) cx = gw - 1; if (cz >= gh) cz = gh - 1; uint32_t c = (uint32_t)(cz * gw + cx);
      if (pass) cellIdx[cellStart[c] + cc[c]++] = i; else cc[c]++; }
  }
  pcellStart = calloc(nc + 1, 4); pcellIdx = malloc(npc * 4); memset(cc, 0, nc * 4);
  for (int pass = 0; pass < 2; pass++) {
    if (pass) { uint32_t s = 0; for (uint32_t c = 0; c < nc; c++) { pcellStart[c] = s; s += cc[c]; cc[c] = 0; } pcellStart[nc] = s; }
    for (uint32_t i = 0; i < npc; i++) { int cx, cz; gcell(pc[i].c[0], pc[i].c[2], &cx, &cz);
      if (cx < 0) cx = 0; if (cz < 0) cz = 0; if (cx >= gw) cx = gw - 1; if (cz >= gh) cz = gh - 1; uint32_t c = (uint32_t)(cz * gw + cx);
      if (pass) pcellIdx[pcellStart[c] + cc[c]++] = i; else cc[c]++; }
  }
  free(cc);
}

typedef struct { float x, y, z; } V3;
typedef struct { float e[3], f[3], r[3], u[3], tx, ty; } Cam;
static void camMake(Cam *k, float ex, float ey, float ez, float yaw, float pitch) {
  k->e[0] = ex; k->e[1] = ey; k->e[2] = ez;
  float cp = cosf(pitch); k->f[0] = sinf(yaw) * cp; k->f[1] = sinf(pitch); k->f[2] = cosf(yaw) * cp;
  k->r[0] = cosf(yaw); k->r[1] = 0.f; k->r[2] = -sinf(yaw);   // вправо по горизонту
  k->u[0] = k->r[1] * k->f[2] - k->r[2] * k->f[1]; k->u[1] = k->r[2] * k->f[0] - k->r[0] * k->f[2]; k->u[2] = k->r[0] * k->f[1] - k->r[1] * k->f[0];
  if (k->u[1] < 0.f) for (int i = 0; i < 3; i++) k->u[i] = -k->u[i];
  k->ty = tanf(FOVY_DEG * (float)M_PI / 360.f); k->tx = k->ty * (480.f / 272.f);
}
static V3 toCam(const Cam *k, const float *p) { float d[3] = {p[0] - k->e[0], p[1] - k->e[1], p[2] - k->e[2]};
  V3 v = {d[0] * k->r[0] + d[1] * k->r[1] + d[2] * k->r[2], d[0] * k->u[0] + d[1] * k->u[1] + d[2] * k->u[2], d[0] * k->f[0] + d[1] * k->f[1] + d[2] * k->f[2]}; return v; }

static void rasterTri(float *zb, V3 a, V3 b, V3 c, const Cam *k) {   // треугольник в осях камеры, все z >= ZNEAR
  float sx[3], sy[3], iz[3]; V3 v[3] = {a, b, c};
  for (int i = 0; i < 3; i++) { iz[i] = 1.f / v[i].z; sx[i] = (v[i].x * iz[i] / k->tx * .5f + .5f) * W; sy[i] = (.5f - v[i].y * iz[i] / k->ty * .5f) * H; }
  float minx = fminf(sx[0], fminf(sx[1], sx[2])), maxx = fmaxf(sx[0], fmaxf(sx[1], sx[2])), miny = fminf(sy[0], fminf(sy[1], sy[2])), maxy = fmaxf(sy[0], fmaxf(sy[1], sy[2]));
  int x0 = (int)fmaxf(0.f, floorf(minx)), x1 = (int)fminf(W - 1.f, ceilf(maxx)), y0 = (int)fmaxf(0.f, floorf(miny)), y1 = (int)fminf(H - 1.f, ceilf(maxy));
  if (x0 > x1 || y0 > y1) return;
  float area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]); if (fabsf(area) < 1e-6f) return;
  float ia = 1.f / area;
  for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
    float px = x + .5f, py = y + .5f;
    float w0 = ((sx[1] - px) * (sy[2] - py) - (sx[2] - px) * (sy[1] - py)) * ia, w1 = ((sx[2] - px) * (sy[0] - py) - (sx[0] - px) * (sy[2] - py)) * ia, w2 = 1.f - w0 - w1;
    if (w0 < 0.f || w1 < 0.f || w2 < 0.f) continue;
    float z = 1.f / (w0 * iz[0] + w1 * iz[1] + w2 * iz[2]);
    if (z < zb[y * W + x]) zb[y * W + x] = z;
  }
}
static void drawTri(float *zb, const float *t, const Cam *k) {
  V3 v[3] = {toCam(k, t), toCam(k, t + 3), toCam(k, t + 6)};
  int in = (v[0].z >= ZNEAR) + (v[1].z >= ZNEAR) + (v[2].z >= ZNEAR); if (!in) return;
  for (int i = 0; i < 3; i++) if (v[i].z > DMAX + 40.f && v[(i + 1) % 3].z > DMAX + 40.f && v[(i + 2) % 3].z > DMAX + 40.f) return;
  if (in == 3) { rasterTri(zb, v[0], v[1], v[2], k); return; }
  V3 o[4]; int n = 0;   // срез по ближней плоскости
  for (int i = 0; i < 3; i++) { V3 p = v[i], q = v[(i + 1) % 3];
    if (p.z >= ZNEAR) o[n++] = p;
    if ((p.z >= ZNEAR) != (q.z >= ZNEAR)) { float s = (ZNEAR - p.z) / (q.z - p.z); V3 m = {p.x + (q.x - p.x) * s, p.y + (q.y - p.y) * s, ZNEAR}; o[n++] = m; } }
  for (int i = 1; i + 1 < n; i++) rasterTri(zb, o[0], o[i], o[i + 1], k);
}
static int sphereInView(const Cam *k, const float *c, float r) {
  V3 v = toCam(k, c); if (v.z < -r) return 0;
  float kx = sqrtf(1.f + k->tx * k->tx), ky = sqrtf(1.f + k->ty * k->ty);
  return fabsf(v.x) - k->tx * v.z <= r * kx && fabsf(v.y) - k->ty * v.z <= r * ky;
}

static void *work(void *arg) {
  long id = (long)arg; float *zb = malloc(W * H * 4); char line[512];
  for (uint32_t p = (uint32_t)id; p < npt; p += (uint32_t)nthreads) {
    const float *g = pt + p * 3;
    for (int hI = 0; hI < 2; hI++) for (int d = 0; d < NDIR; d++) {
      Cam k; camMake(&k, g[0], g[1] + EYEH[hI], g[2], (float)d * (2.f * (float)M_PI / NDIR), -10.f * (float)M_PI / 180.f);
      for (int i = 0; i < W * H; i++) zb[i] = 1e30f;
      int cx0, cz0; gcell(g[0], g[2], &cx0, &cz0); int rc = (int)ceilf(DMAX / GRID) + 1;
      long ptris[3][3] = {{0}}, ppc[3] = {0};
      for (int cz = cz0 - rc; cz <= cz0 + rc; cz++) for (int cx = cx0 - rc; cx <= cx0 + rc; cx++) {
        if (cx < 0 || cz < 0 || cx >= gw || cz >= gh) continue;
        float cc[3] = {gx0 + (cx + .5f) * GRID, g[1], gz0 + (cz + .5f) * GRID};
        float dxz = hypotf(cc[0] - g[0], cc[2] - g[2]); if (dxz > DMAX + GRID) continue;
        uint32_t c = (uint32_t)(cz * gw + cx);
        for (uint32_t j = cellStart[c]; j < cellStart[c + 1]; j++) drawTri(zb, tri + cellIdx[j] * 9, &k);
        for (uint32_t j = pcellStart[c]; j < pcellStart[c + 1]; j++) { const Pc *q = &pc[pcellIdx[j]]; if (!q->n[0]) continue;
          float dist = sqrtf((q->c[0] - k.e[0]) * (q->c[0] - k.e[0]) + (q->c[1] - k.e[1]) * (q->c[1] - k.e[1]) + (q->c[2] - k.e[2]) * (q->c[2] - k.e[2])) - q->c[3];
          if (dist < 0.f) dist = 0.f;
          if (!sphereInView(&k, q->c, q->c[3])) continue;
          for (int di = 0; di < 3; di++) { if (dist > DD_[di]) continue; if (di == 2) {} ppc[di]++;
            for (int fi = 0; fi < 3; fi++) ptris[fi][di] += dist > FPS_[fi] ? q->n[1] : q->n[0]; } }
      }
      long bins[6] = {0}, sky = 0;
      for (int i = 0; i < W * H; i++) { float z = zb[i]; if (z >= 1e29f) { sky++; continue; } for (int b = 0; b < 6; b++) if (z < BIN[b]) { bins[b]++; break; } }
      int n = snprintf(line, sizeof line, "%u,%.1f,%.1f,%.1f,%d,%d,%ld,%ld,%ld,%ld,%ld,%ld", p, g[0], g[1], g[2], hI, d, bins[0], bins[1], bins[2], bins[3], bins[4] + bins[5], sky);
      for (int fi = 0; fi < 3; fi++) for (int di = 0; di < 3; di++) n += snprintf(line + n, sizeof line - (size_t)n, ",%ld", ptris[fi][di]);
      n += snprintf(line + n, sizeof line - (size_t)n, ",%ld,%ld,%ld\n", ppc[0], ppc[1], ppc[2]);
      pthread_mutex_lock(&mx); fputs(line, outf); pthread_mutex_unlock(&mx);
    }
  }
  free(zb); return 0;
}

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "scout IN.bin OUT.csv [потоков]\n"); return 1; }
  if (argc > 3) nthreads = atoi(argv[3]);
  FILE *f = fopen(argv[1], "rb"); if (!f) { perror(argv[1]); return 1; }
  char mg[4]; uint32_t h[3]; if (fread(mg, 1, 4, f) != 4 || memcmp(mg, "SCT1", 4) || fread(h, 4, 3, f) != 3) { fprintf(stderr, "не SCT1\n"); return 1; }
  ntri = h[0]; npc = h[1]; npt = h[2];
  tri = malloc((size_t)ntri * 36); tpc = malloc((size_t)ntri * 4); pc = malloc((size_t)npc * sizeof(Pc)); pt = malloc((size_t)npt * 12);
  if (fread(tri, 36, ntri, f) != ntri || fread(tpc, 4, ntri, f) != ntri || fread(pc, sizeof(Pc), npc, f) != npc || fread(pt, 12, npt, f) != npt) { fprintf(stderr, "короткий файл\n"); return 1; }
  fclose(f); buildGrid();
  outf = fopen(argv[2], "w");
  fprintf(outf, "point,x,y,z,eye,dir,px40,px90,px140,px200,px250,sky");
  for (int fi = 0; fi < 3; fi++) for (int di = 0; di < 3; di++) fprintf(outf, ",tris_fp%d_d%d", (int)FPS_[fi], (int)DD_[di]);
  fprintf(outf, ",pieces_d150,pieces_d200,pieces_d250\n");
  pthread_t th[64]; if (nthreads > 64) nthreads = 64;
  for (long i = 0; i < nthreads; i++) pthread_create(&th[i], 0, work, (void *)i);
  for (int i = 0; i < nthreads; i++) pthread_join(th[i], 0);
  fclose(outf); fprintf(stderr, "ракурсов: %u\n", npt * 2 * NDIR); return 0;
}
