// Хост-растеризатор для снимков вида (tools/autoexplore/tracks/hostshot.py): треугольники в пространстве камеры, обрезка по ближней плоскости,
// z-буфер по 1/z, перспективно-верная текстура (ближайший тексель, повтор), цвет вершины x текстура, альфа-тест 0x40 и смешивание.
//   cc -O2 -shared -fPIC rast.c -o librast.dylib
#include <math.h>
#include <stdint.h>
#include <string.h>
typedef struct { float x, y, z, u, v, r, g, b, a; } V;
typedef struct { const int *toff, *tw, *th; const uint8_t *tex; int W, H; float fx, fy; uint8_t *rgb; float *zb; int fl; int tex_i; int *idb; int id; } Ctx;
static V lerpv(V a, V b, float t) { V o; float *pa = (float *)&a, *pb = (float *)&b, *po = (float *)&o; for (int i = 0; i < 9; i++) po[i] = pa[i] + (pb[i] - pa[i]) * t; return o; }
static void tri(const Ctx *c, V a, V b, V d) {
  float W = (float)c->W, H = (float)c->H, sx[3], sy[3], iw[3], uu[3], vv[3]; V p[3] = {a, b, d};
  for (int i = 0; i < 3; i++) { float z = p[i].z; iw[i] = 1.f / z; sx[i] = W * .5f + c->fx * p[i].x * iw[i]; sy[i] = H * .5f - c->fy * p[i].y * iw[i]; uu[i] = p[i].u * iw[i]; vv[i] = p[i].v * iw[i]; }
  float minx = fminf(sx[0], fminf(sx[1], sx[2])), maxx = fmaxf(sx[0], fmaxf(sx[1], sx[2])), miny = fminf(sy[0], fminf(sy[1], sy[2])), maxy = fmaxf(sy[0], fmaxf(sy[1], sy[2]));
  int x0 = (int)fmaxf(0.f, floorf(minx)), x1 = (int)fminf(W - 1, ceilf(maxx)), y0 = (int)fmaxf(0.f, floorf(miny)), y1 = (int)fminf(H - 1, ceilf(maxy));
  if (x0 > x1 || y0 > y1) return;
  float area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]); if (fabsf(area) < 1e-6f) return;
  float ia = 1.f / area; int ti = c->tex_i; int blend = c->fl & 2, atest = c->fl & 1;
  for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
    float px = x + .5f, py = y + .5f;
    float w0 = ((sx[1] - px) * (sy[2] - py) - (sx[2] - px) * (sy[1] - py)) * ia, w1 = ((sx[2] - px) * (sy[0] - py) - (sx[0] - px) * (sy[2] - py)) * ia, w2 = 1.f - w0 - w1;
    if (w0 < -1e-4f || w1 < -1e-4f || w2 < -1e-4f) continue;
    float q = w0 * iw[0] + w1 * iw[1] + w2 * iw[2]; float *zp = &c->zb[y * c->W + x]; if (q <= *zp) continue;
    float u = (w0 * uu[0] + w1 * uu[1] + w2 * uu[2]) / q, v = (w0 * vv[0] + w1 * vv[1] + w2 * vv[2]) / q;
    float r = w0 * p[0].r + w1 * p[1].r + w2 * p[2].r, g = w0 * p[0].g + w1 * p[1].g + w2 * p[2].g, bl = w0 * p[0].b + w1 * p[1].b + w2 * p[2].b, al = w0 * p[0].a + w1 * p[1].a + w2 * p[2].a;
    if (ti >= 0) { int tw = c->tw[ti], th = c->th[ti]; int tx = ((int)floorf(u * tw)) % tw, ty = ((int)floorf(v * th)) % th; if (tx < 0) tx += tw; if (ty < 0) ty += th;
      const uint8_t *t = c->tex + c->toff[ti] + 4 * (ty * tw + tx); r *= t[0] / 255.f; g *= t[1] / 255.f; bl *= t[2] / 255.f; al *= t[3] / 255.f; }
    if (atest && al < 0.25f) continue;
    uint8_t *o = c->rgb + 3 * (y * c->W + x); float R = fminf(1.f, r) * 255.f, G = fminf(1.f, g) * 255.f, B = fminf(1.f, bl) * 255.f;
    if (blend) { float a = fminf(1.f, al); o[0] = (uint8_t)(R * a + o[0] * (1 - a)); o[1] = (uint8_t)(G * a + o[1] * (1 - a)); o[2] = (uint8_t)(B * a + o[2] * (1 - a)); }
    else { o[0] = (uint8_t)R; o[1] = (uint8_t)G; o[2] = (uint8_t)B; *zp = q; if (c->idb) c->idb[y * c->W + x] = c->id; }
  }
}
// vv: ntri*3 вершин в пространстве камеры (x вправо, y вверх, z вперёд), pass 0 — непрозрачные, 1 — смешиваемые (по порядку массива). Возврат: число нарисованных треугольников
int render(int ntri, const float *vv, const int *texi, const int *fl, const int *toff, const int *tw, const int *th, const uint8_t *tex, int W, int H, float fx, float fy, float nearz, uint8_t *rgb, float *zb, int pass, int *idb) {
  int drawn = 0; Ctx c = {toff, tw, th, tex, W, H, fx, fy, rgb, zb, 0, -1, idb, 0};
  for (int i = 0; i < ntri; i++) {
    int f = fl[i]; if (((f & 2) != 0) != (pass == 1)) continue; c.fl = f; c.tex_i = texi[i]; c.id = i;
    V p[3]; memcpy(p, vv + i * 27, sizeof p);
    V in[4]; int n = 0;
    for (int k = 0; k < 3; k++) { V a = p[k], b = p[(k + 1) % 3]; int ia = a.z >= nearz, ib = b.z >= nearz;
      if (ia) in[n++] = a;
      if (ia != ib && n < 4) { float t = (nearz - a.z) / (b.z - a.z); in[n++] = lerpv(a, b, t); } }
    if (n < 3) continue;
    tri(&c, in[0], in[1], in[2]); if (n == 4) tri(&c, in[0], in[2], in[3]); drawn++;
  }
  return drawn;
}

// Видимость кусков (PVS по курсу, tools/pvs2.py): треугольники уже в мировых координатах (tri: ntri*9 float), piece_of_tri не нужен — куски заданы диапазонами
// pstart/pcount по общему массиву. sel — номера кусков для кадра; камера: eye, оси s (вправо), u (вверх), f (вперёд). Результат: idb[y*W+x] = номер куска (или -1).
// Куски с flags & 3 (альфа-тест, смешивание) глубину не пишут (не закрывают); если прошли тест глубины против непрозрачных — mark[кусок] = 1. Видимые = уникальные idb + mark.
typedef struct { int W, H; float fx, fy, nz; int *idb; float *zb; unsigned char *mark; } IdCtx;
static void idtri(const IdCtx *c, V a, V b, V d, int id, int writez) {
  float W = (float)c->W, H = (float)c->H, sx[3], sy[3], iw[3]; V p[3] = {a, b, d};
  for (int i = 0; i < 3; i++) { iw[i] = 1.f / p[i].z; sx[i] = W * .5f + c->fx * p[i].x * iw[i]; sy[i] = H * .5f - c->fy * p[i].y * iw[i]; }
  float minx = fminf(sx[0], fminf(sx[1], sx[2])), maxx = fmaxf(sx[0], fmaxf(sx[1], sx[2])), miny = fminf(sy[0], fminf(sy[1], sy[2])), maxy = fmaxf(sy[0], fmaxf(sy[1], sy[2]));
  int x0 = (int)fmaxf(0.f, floorf(minx)), x1 = (int)fminf(W - 1, ceilf(maxx)), y0 = (int)fmaxf(0.f, floorf(miny)), y1 = (int)fminf(H - 1, ceilf(maxy));
  if (x0 > x1 || y0 > y1) return;
  float area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]); if (fabsf(area) < 1e-9f) return; float ia = 1.f / area;
  for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
    float px = x + .5f, py = y + .5f;
    float w0 = ((sx[1] - px) * (sy[2] - py) - (sx[2] - px) * (sy[1] - py)) * ia, w1 = ((sx[2] - px) * (sy[0] - py) - (sx[0] - px) * (sy[2] - py)) * ia, w2 = 1.f - w0 - w1;
    if (w0 < -1e-4f || w1 < -1e-4f || w2 < -1e-4f) continue;
    float q = w0 * iw[0] + w1 * iw[1] + w2 * iw[2]; float *zp = &c->zb[y * c->W + x]; if (q <= *zp) continue;
    if (writez) { *zp = q; c->idb[y * c->W + x] = id; } else c->mark[id] = 1;
  }
}
// сначала непрозрачные (pass 0), потом остальные (pass 1: не пишут глубину; id ставят только в пустой пиксель — расширение списка, не замена)
int render_ids(int nsel, const int *sel, const int *pstart, const int *pcount, const int *pflags, const float *tri, int W, int H, float fx, float fy, float nearz,
               const float *eye, const float *s, const float *u, const float *f, int *idb, float *zb, unsigned char *mark) {
  IdCtx c = {W, H, fx, fy, nearz, idb, zb, mark}; int drawn = 0;
  for (int pass = 0; pass < 2; pass++) for (int k = 0; k < nsel; k++) {
    int pi = sel[k]; int nonopq = (pflags[pi] & 3) != 0; if ((pass == 1) != nonopq) continue;
    const float *T = tri + (size_t)pstart[pi] * 9;
    for (int t = 0; t < pcount[pi]; t++, T += 9) {
      V p[3]; for (int j = 0; j < 3; j++) { float rx = T[3 * j] - eye[0], ry = T[3 * j + 1] - eye[1], rz = T[3 * j + 2] - eye[2];
        p[j].x = rx * s[0] + ry * s[1] + rz * s[2]; p[j].y = rx * u[0] + ry * u[1] + rz * u[2]; p[j].z = rx * f[0] + ry * f[1] + rz * f[2]; p[j].u = p[j].v = p[j].r = p[j].g = p[j].b = p[j].a = 0; }
      V in[4]; int n = 0;
      for (int q = 0; q < 3; q++) { V a = p[q], b = p[(q + 1) % 3]; int ia = a.z >= nearz, ib = b.z >= nearz; if (ia) in[n++] = a; if (ia != ib && n < 4) { float tt = (nearz - a.z) / (b.z - a.z); in[n++] = lerpv(a, b, tt); } }
      if (n < 3) continue;
      idtri(&c, in[0], in[1], in[2], pi, !nonopq); if (n == 4) idtri(&c, in[0], in[2], in[3], pi, !nonopq); drawn++;
    }
  }
  return drawn;
}
