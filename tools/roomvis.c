// roomvis.c: видимость треугольников комнаты программным растром с глубиной (правка Роба 27: камеры комнат за стенами).
// Лицевая сторона — как в движке и tools/wind.c: CCW, dot((b−a)×(c−a), глаз − a) > 0 (sceGuFrontFace(GU_CCW)).
//
//   roomvis vote TRIS EYES OUT [--res 64]
//     из каждого глаза — куб 6 граней RES×RES, в каждом пикселе первый треугольник (все рисуются с обеих сторон);
//     OUT: u32 front[ntri], u32 back[ntri] — сколько пикселей треугольник занял лицом / изнанкой к глазу
//   roomvis view TRIS VIEWS OUT [--w 160 --h 90]
//     кадры камер: глаз, точка взгляда, вертикальный FOV (градусы), отношение сторон; треугольник рисуется с обеих сторон,
//     если его флаг & 1, иначе только лицом; OUT по кадру: u32 пикселей всего, пустых, «изнутри наружу» (первым виден
//     треугольник, у которого сторона к глазу помечена как наружная: side[] = +1 — наружу смотрит изнанка, −1 — лицо)
// Файлы: TRIS = u32 n, f32[9n] вершины, u8[n] флаги, i8[n] side; EYES = u32 n, f32[3n]; VIEWS = u32 n, f32[8n]
//   (eye xyz, look xyz, fovy, aspect).
//   roomvis seen TRIS VIEWS OUT [--w 160 --h 90 --max 0.10]
//     правка Роба 301 (спинка телевизора — «просто рамка»): кадры камер, ВСЕ треугольники с обеих сторон (что было бы видно,
//     рисуй движок всё); «изнанкой» — первым в пикселе виден треугольник без флага & 1 (рисуется только лицом) своей изнанкой:
//     движок его отсекает, кадр видит сквозь него. Кадр, где таких пикселей больше --max доли, — камера за стеной (так стоят
//     камеры оригинала, правка 27): не в счёт. OUT: u32 изнанкой[ntri] (сумма по кадрам в счёт), u32 изнанкой[nview] (каждый кадр)
// Сборка: cc -O3 -o build/roomvis tools/roomvis.c -lm
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

static uint32_t NT; static float *V; static uint8_t *FLG; static int8_t *SIDE;
static int W = 64, H = 64;
static float SEEN_MAX = .10f;   // seen: доля кадра «изнанкой», выше — камера за стеной, кадр не в счёт
static float *ZB; static int32_t *ID;   // глубина 1/w (больше — ближе), номер треугольника | 0x40000000 если лицом

static void *rd(const char *path, size_t *n) {
  FILE *f = fopen(path, "rb"); if (!f) { perror(path); exit(1); }
  fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
  void *b = malloc(*n ? *n : 1); if (fread(b, 1, *n, f) != *n) { fprintf(stderr, "read %s\n", path); exit(1); } fclose(f); return b;
}
// треугольник в пространстве камеры (x вправо, y вверх, w вперёд — уже поделены на тангенсы половин угла): отсечение по
// ближней плоскости w >= NEAR, растр по центрам пикселей
#define NEARW 0.05f
static void raster(const float q[3][3], int32_t id) {
  float poly[5][3]; int np = 0;
  if (q[0][2] < NEARW && q[1][2] < NEARW && q[2][2] < NEARW) return;
  for (int k = 0; k < 3; k++) {
    const float *a = q[k], *b = q[(k + 1) % 3]; int ia = a[2] >= NEARW, ib = b[2] >= NEARW;
    if (ia) { memcpy(poly[np], a, 12); np++; }
    if (ia != ib) { float t = (NEARW - a[2]) / (b[2] - a[2]); for (int j = 0; j < 3; j++) poly[np][j] = a[j] + (b[j] - a[j]) * t; np++; }
  }
  float s[5][3];
  for (int k = 0; k < np; k++) { float iw = 1.f / poly[k][2]; s[k][0] = (poly[k][0] * iw + 1.f) * .5f * W; s[k][1] = (poly[k][1] * iw + 1.f) * .5f * H; s[k][2] = iw; }
  for (int k = 1; k + 1 < np; k++) {
    double x0 = s[0][0], y0 = s[0][1], x1 = s[k][0], y1 = s[k][1], x2 = s[k + 1][0], y2 = s[k + 1][1];
    double det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0); if (fabs(det) < 1e-12) continue;
    int px0 = (int)fmax(0, ceil(fmin(x0, fmin(x1, x2)) - .5)), px1 = (int)fmin(W - 1, floor(fmax(x0, fmax(x1, x2)) - .5));
    int py0 = (int)fmax(0, ceil(fmin(y0, fmin(y1, y2)) - .5)), py1 = (int)fmin(H - 1, floor(fmax(y0, fmax(y1, y2)) - .5));
    if (px0 > px1 || py0 > py1) continue;
    double zA = ((s[k][2] - s[0][2]) * (y2 - y0) - (s[k + 1][2] - s[0][2]) * (y1 - y0)) / det;
    double zB = ((x1 - x0) * (s[k + 1][2] - s[0][2]) - (x2 - x0) * (s[k][2] - s[0][2])) / det;
    for (int py = py0; py <= py1; py++) for (int px = px0; px <= px1; px++) {
      double x = px + .5, y = py + .5;
      double w0 = (x1 - x) * (y2 - y) - (x2 - x) * (y1 - y), w1 = (x2 - x) * (y0 - y) - (x0 - x) * (y2 - y), w2 = (x0 - x) * (y1 - y) - (x1 - x) * (y0 - y);
      if (det > 0 ? (w0 < 0 || w1 < 0 || w2 < 0) : (w0 > 0 || w1 > 0 || w2 > 0)) continue;
      float z = (float)(s[0][2] + zA * (x - x0) + zB * (y - y0)); int o = py * W + px;
      if (z <= ZB[o]) continue; ZB[o] = z; ID[o] = id;
    }
  }
}
// все треугольники в кадр: базис камеры r,u,f (единичные), tx, ty — тангенсы половин углов; cull — рисовать только лицом
static void frame(const float e[3], const float r[3], const float u[3], const float f[3], float tx, float ty, int useFlags) {
  for (int i = 0; i < W * H; i++) { ZB[i] = 0.f; ID[i] = -1; }
  for (uint32_t t = 0; t < NT; t++) {
    const float *a = V + 9 * t, *b = a + 3, *c = a + 6;
    float ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
    float nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    float sd = nx * (e[0] - a[0]) + ny * (e[1] - a[1]) + nz * (e[2] - a[2]);
    if (sd == 0.f) continue;
    int front = sd > 0.f;
    if (useFlags && !(FLG[t] & 1) && !front) continue;   // рисуется только лицом
    float q[3][3];
    for (int k = 0; k < 3; k++) {
      const float *p = a + 3 * k; float dx = p[0] - e[0], dy = p[1] - e[1], dz = p[2] - e[2];
      q[k][0] = (dx * r[0] + dy * r[1] + dz * r[2]) / tx; q[k][1] = (dx * u[0] + dy * u[1] + dz * u[2]) / ty; q[k][2] = dx * f[0] + dy * f[1] + dz * f[2];
    }
    raster(q, (int32_t)t | (front ? 0x40000000 : 0));
  }
}
static void basis(const float f0[3], const float up0[3], float r[3], float u[3], float f[3]) {
  float l = sqrtf(f0[0] * f0[0] + f0[1] * f0[1] + f0[2] * f0[2]); for (int i = 0; i < 3; i++) f[i] = f0[i] / l;
  r[0] = f[1] * up0[2] - f[2] * up0[1]; r[1] = f[2] * up0[0] - f[0] * up0[2]; r[2] = f[0] * up0[1] - f[1] * up0[0];
  l = sqrtf(r[0] * r[0] + r[1] * r[1] + r[2] * r[2]); if (l < 1e-6f) { r[0] = 1; r[1] = r[2] = 0; l = 1; } for (int i = 0; i < 3; i++) r[i] /= l;
  u[0] = r[1] * f[2] - r[2] * f[1]; u[1] = r[2] * f[0] - r[0] * f[2]; u[2] = r[0] * f[1] - r[1] * f[0];
}

int main(int argc, char **argv) {
  if (argc < 5) { fprintf(stderr, "usage: roomvis vote|view|seen TRIS EYES|VIEWS OUT [--res N | --w W --h H]\n"); return 2; }
  for (int i = 5; i + 1 < argc; i++) {
    if (!strcmp(argv[i], "--res")) W = H = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--w")) W = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--h")) H = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--max")) SEEN_MAX = (float)atof(argv[++i]);
  }
  size_t n; uint8_t *tb = rd(argv[2], &n); memcpy(&NT, tb, 4);
  V = (float *)(tb + 4); FLG = tb + 4 + 36 * (size_t)NT; SIDE = (int8_t *)(FLG + NT);
  ZB = malloc(sizeof(float) * W * H); ID = malloc(sizeof(int32_t) * W * H);
  size_t m; uint8_t *eb = rd(argv[3], &m); uint32_t ne; memcpy(&ne, eb, 4); const float *E = (const float *)(eb + 4);
  FILE *o = fopen(argv[4], "wb"); if (!o) { perror(argv[4]); return 1; }
  if (!strcmp(argv[1], "vote")) {
    uint32_t *cf = calloc(NT, 4), *cb = calloc(NT, 4);
    static const float F[6][3] = {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}};
    static const float UP[6][3] = {{0, 1, 0}, {0, 1, 0}, {0, 0, 1}, {0, 0, 1}, {0, 1, 0}, {0, 1, 0}};
    for (uint32_t k = 0; k < ne; k++)
      for (int fc = 0; fc < 6; fc++) {
        float r[3], u[3], f[3]; basis(F[fc], UP[fc], r, u, f);
        frame(E + 3 * k, r, u, f, 1.f, 1.f, 0);
        for (int i = 0; i < W * H; i++) { if (ID[i] < 0) continue; uint32_t t = ID[i] & 0x3FFFFFFF; if (ID[i] & 0x40000000) cf[t]++; else cb[t]++; }
      }
    fwrite(cf, 4, NT, o); fwrite(cb, 4, NT, o);
  } else if (!strcmp(argv[1], "seen")) {
    uint32_t *acc = calloc(NT, 4), *pv = calloc(ne ? ne : 1, 4), *cur = calloc(NT, 4);
    for (uint32_t k = 0; k < ne; k++) {
      const float *v = E + 8 * k; float fw[3] = {v[3] - v[0], v[4] - v[1], v[5] - v[2]}, up0[3] = {0, 1, 0}, r[3], u[3], f[3];
      basis(fw, up0, r, u, f);
      float ty = tanf(v[6] * 3.14159265f / 360.f), tx = ty * v[7];
      frame(v, r, u, f, tx, ty, 0);   // всё с обеих сторон
      uint32_t bad = 0;
      for (int i = 0; i < W * H; i++) {
        if (ID[i] < 0) continue;
        uint32_t t = ID[i] & 0x3FFFFFFF; int front = (ID[i] & 0x40000000) != 0;
        if (!(FLG[t] & 1) && !front) { bad++; cur[t]++; }
      }
      pv[k] = bad;
      if (bad <= SEEN_MAX * W * H) { for (uint32_t t = 0; t < NT; t++) acc[t] += cur[t]; }
      memset(cur, 0, 4 * (size_t)NT);
    }
    fwrite(acc, 4, NT, o); fwrite(pv, 4, ne, o);
  } else {
    for (uint32_t k = 0; k < ne; k++) {
      const float *v = E + 8 * k; float fw[3] = {v[3] - v[0], v[4] - v[1], v[5] - v[2]}, up0[3] = {0, 1, 0}, r[3], u[3], f[3];
      basis(fw, up0, r, u, f);
      float ty = tanf(v[6] * 3.14159265f / 360.f), tx = ty * v[7];
      frame(v, r, u, f, tx, ty, 1);
      uint32_t tot = W * H, empty = 0, outer = 0;
      for (int i = 0; i < W * H; i++) {
        if (ID[i] < 0) { empty++; continue; }
        uint32_t t = ID[i] & 0x3FFFFFFF; int front = (ID[i] & 0x40000000) != 0;
        if ((SIDE[t] > 0 && !front) || (SIDE[t] < 0 && front)) outer++;
      }
      uint32_t rec[3] = {tot, empty, outer}; fwrite(rec, 4, 3, o);
    }
  }
  fclose(o);
  return 0;
}
