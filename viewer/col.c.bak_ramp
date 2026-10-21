// Коллизия уровня по секции COL1 — см. col.h. Чистый C99, float, одна аллокация в colInit.
//
// Как устроено:
//  * земля (colGround): вертикальный луч в одной клетке сетки 4 м — треугольники с n.y > 0.5 (точка в треугольнике
//    по xz + высота плоскости), ящики (луч против OBB, берём грань входа, если она проходимая), цилиндры/капсулы/сферы;
//  * кузов (colPushCar): прямоугольник в xz и твёрдый слой [пол+lo, пол+hi] (пол — плоскость под колёсами, может
//    быть наклонной). Каждый примитив режется этим слоем, срез проецируется в xz: выпуклый набор точек (+ радиус
//    у капсул/сфер) и оси для SAT. Забор — толстый (FENCE_D) четырёхугольник за линией, SAT с допустимыми
//    направлениями: никогда внутрь (на изнанку), вдоль забора — только за выпуклый/свободный конец; стыки звеньев
//    без выпуклого излома продлены на FENCE_EXT и вдоль не толкают (иначе машина цеплялась бы за стыки).
//    Выталкиваем итерациями: каждый раз самый глубокий контакт, потом пересчёт всех.
#include "col.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#ifdef COL_DEBUG
#include <stdio.h>
int colDebug = 0;
long colStat[4];   // вызовы: gather, colGround, colCrossFence, итерации выталкивания
#define STAT(k) colStat[k]++
#else
#define STAT(k)
#endif

#define MAXSHAPE 128        // примитивов в узкой фазе за один запрос (обычно 0..20)
#define MAXP 32             // точек среза у одной фигуры (ящик: 8 углов + 24 пересечения рёбер с плоскостями)
#define MAXA 8              // собственных осей SAT у фигуры
#define GATHER_MARGIN 0.6f  // запас широкой фазы: кузов может сдвинуться за итерации
#define FENCE_EXT 2.0f      // продление забора за стык без выпуклого излома
#define FENCE_D 6.0f        // толщина забора «за линией» для SAT
#define PUSH_EPS 1e-4f
#define MAX_ITER 8
#define TRI_EDGE_EPS 2e-3f  // точка на ребре треугольника земли с запасом 2 мм (щели между соседними)
#define GRAZE 0.02f        // примитив заходит в слой кузова меньше чем на 2 см сверху/снизу — не стена (иначе
                            // верх ящика вровень с низом слоя даёт тонкий срез на всю площадь и толчок вбок)

enum { SH_CONVEX = 0, SH_FENCE = 1 };
enum { SF_CVX_A = 1, SF_CVX_B = 2, SF_EXT_A = 4, SF_EXT_B = 8 };   // флаги концов заборов (строятся в colInit)

typedef struct {
  unsigned char kind, ptype, np, na;
  uint32_t idx;
  float rad;
  float fa[2], fd[2], fn[2], L, t0, t1;   // забор: начало, направление, нормаль, длина, пределы вдоль
  unsigned char fflags;                   // SF_* концов
  float p[MAXP][2];                       // выпуклая фигура: точки среза (xz)
  float a[MAXA][2];                       // оси SAT (единичные)
} Shape;

struct ColScratch {
  uint16_t *stamp; uint16_t cur;
  uint8_t *segFlags;
  uint8_t *steep;           // бит на треугольник: n.y <= COL_WALK_NY (стена) — чтобы не читать землю в широкой фазе
  int nshape;
  Shape shape[MAXSHAPE];
};

static float fminf_(float a, float b) { return a < b ? a : b; }
static float fmaxf_(float a, float b) { return a > b ? a : b; }

const char *colError(int code) {
  switch (code) {
  case 0: return "ok";
  case -1: return "COL1: section too small";
  case -2: return "COL1: section not 4-byte aligned";
  case -3: return "COL1: bad magic";
  case -4: return "COL1: bad grid";
  case -5: return "COL1: arrays exceed section size";
  case -6: return "COL1: cellStart broken";
  case -7: return "COL1: bad reference";
  case -8: return "COL1: out of memory";
  default: return "COL1: unknown error";
  }
}

// ---------------------------------------------------------------------------------------------- заборы: стыки
typedef struct { float x, z; uint32_t id; } EndPt;   // id = seg*2 + конец (0 = a, 1 = b)
static int cmpEnd(const void *a, const void *b) {
  float d = ((const EndPt *)a)->x - ((const EndPt *)b)->x; return d < 0 ? -1 : d > 0;
}
static int fenceFlags(ColWorld *w) {
  uint32_t n = w->nseg; uint8_t *fl = w->scr->segFlags;
  if (!n) return 0;
  EndPt *e = (EndPt *)malloc(sizeof(EndPt) * 2 * n);
  int32_t *nb = (int32_t *)malloc(sizeof(int32_t) * 2 * n);
  if (!e || !nb) { free(e); free(nb); return -8; }
  for (uint32_t i = 0; i < n; i++) {
    const ColSeg *s = &w->seg[i];
    e[2 * i] = (EndPt){s->a[0], s->a[1], 2 * i}; e[2 * i + 1] = (EndPt){s->b[0], s->b[1], 2 * i + 1};
  }
  qsort(e, 2 * n, sizeof(EndPt), cmpEnd);
  for (uint32_t i = 0; i < 2 * n; i++) nb[i] = -1;
  const float tol = 2e-3f;
  for (uint32_t i = 0; i < 2 * n; i++) {
    if (nb[e[i].id] >= 0) continue;
    for (uint32_t j = i + 1; j < 2 * n && e[j].x - e[i].x <= tol; j++) {
      if ((e[j].id >> 1) == (e[i].id >> 1) || nb[e[j].id] >= 0) continue;
      if (fabsf(e[j].z - e[i].z) <= tol) { nb[e[i].id] = (int32_t)e[j].id; nb[e[j].id] = (int32_t)e[i].id; break; }
    }
  }
  for (uint32_t i = 0; i < n; i++) fl[i] = 0;
  for (uint32_t id = 0; id < 2 * n; id++) {
    uint32_t si = id >> 1, end = id & 1;
    const ColSeg *s = &w->seg[si];
    float dx = s->b[0] - s->a[0], dz = s->b[1] - s->a[1], L = sqrtf(dx * dx + dz * dz);
    if (L < 1e-4f) continue;
    int32_t o = nb[id];
    uint8_t pt = end ? SF_CVX_B : SF_CVX_A, ext = end ? SF_EXT_B : SF_EXT_A;
    if (o < 0) { fl[si] |= pt; continue; }                      // свободный конец — угол
    uint32_t sj = (uint32_t)o >> 1, endj = (uint32_t)o & 1;
    const ColSeg *t = &w->seg[sj];
    float ex = t->b[0] - t->a[0], ez = t->b[1] - t->a[1], Lj = sqrtf(ex * ex + ez * ez);
    if (Lj < 1e-4f) { fl[si] |= pt; continue; }
    // направления от общей вершины внутрь каждого звена
    float uix = end ? -dx / L : dx / L, uiz = end ? -dz / L : dz / L;
    float ujx = endj ? -ex / Lj : ex / Lj, ujz = endj ? -ez / Lj : ez / Lj;
    float bx = uix + ujx, bz = uiz + ujz, bl = sqrtf(bx * bx + bz * bz);
    float nx = s->n[0] + t->n[0], nz = s->n[1] + t->n[1];
    if (bl < 0.02f) { fl[si] |= ext; continue; }                 // прямо: продлеваем, угла нет
    if (bx * nx + bz * nz <= 0) fl[si] |= pt;                   // выпуклый угол (непроезжее торчит к дороге)
    else fl[si] |= ext;                                          // вогнутый: полуплоскость продлеваем
  }
  free(e); free(nb);
  return 0;
}

int colInit(ColWorld *w, const void *section, unsigned size) {
  memset(w, 0, sizeof *w);
  if (!section || size < sizeof(ColHdr)) return -1;
  if ((uintptr_t)section & 3) return -2;
  const ColHdr *h = (const ColHdr *)section;
  if (memcmp(h->magic, "COL1", 4)) return -3;
  if (!(h->cell > 0.f) || h->W == 0 || h->H == 0 || h->W > 65536 || h->H > 65536) return -4;
  uint64_t cells = (uint64_t)h->W * h->H;
  uint64_t need = 48 + (uint64_t)h->ntri * 48 + (uint64_t)h->nbox * 64 + (uint64_t)h->ncyl * 48 + (uint64_t)h->nseg * 32 +
                  (cells + 1) * 4 + (uint64_t)h->nref * 4;
  if (need > size) return -5;
  const char *p = (const char *)section + 48;
  w->tri = (const ColTri *)p; p += (size_t)h->ntri * 48;
  w->box = (const ColBox *)p; p += (size_t)h->nbox * 64;
  w->cyl = (const ColCyl *)p; p += (size_t)h->ncyl * 48;
  w->seg = (const ColSeg *)p; p += (size_t)h->nseg * 32;
  w->cellStart = (const uint32_t *)p; p += (size_t)(cells + 1) * 4;
  w->refs = (const uint32_t *)p;
  w->ox = h->ox; w->oz = h->oz; w->cell = h->cell; w->inv = 1.f / h->cell; w->W = (int)h->W; w->H = (int)h->H;
  w->ntri = h->ntri; w->nbox = h->nbox; w->ncyl = h->ncyl; w->nseg = h->nseg; w->nref = h->nref;
  if (w->cellStart[0] != 0 || w->cellStart[cells] != h->nref) return -6;
  for (uint64_t i = 0; i < cells; i++) if (w->cellStart[i] > w->cellStart[i + 1]) return -6;
  uint32_t cnt[4] = {w->ntri, w->nbox, w->ncyl, w->nseg};
  for (uint32_t i = 0; i < w->nref; i++) {
    uint32_t t = w->refs[i] >> 29, k = w->refs[i] & 0x1fffffffu;
    if (t > 3 || k >= cnt[t]) return -7;
  }
  uint32_t nprim = w->ntri + w->nbox + w->ncyl + w->nseg;
  size_t sz = sizeof(ColScratch) + (size_t)nprim * 2 + w->nseg + (w->ntri + 7) / 8 + 16;
  ColScratch *s = (ColScratch *)malloc(sz);
  if (!s) return -8;
  memset(s, 0, sz);
  s->stamp = (uint16_t *)(s + 1); s->segFlags = (uint8_t *)(s->stamp + nprim); s->steep = s->segFlags + w->nseg; s->cur = 0;
  for (uint32_t i = 0; i < w->ntri; i++) if (w->tri[i].n[1] <= COL_WALK_NY) s->steep[i >> 3] |= (uint8_t)(1u << (i & 7));
  w->scr = s;
  int r = fenceFlags(w);
  if (r) { colFree(w); return r; }
  return 0;
}

void colFree(ColWorld *w) { if (w->scr) free(w->scr); w->scr = 0; }

static uint16_t nextStamp(ColScratch *s, uint32_t nprim) {
  if (++s->cur == 0) { memset(s->stamp, 0, (size_t)nprim * 2); s->cur = 1; }
  return s->cur;
}

// ---------------------------------------------------------------------------------------------- земля
int colGround(const ColWorld *w, float x, float z, float yTop, float yBottom, float *outY, float *outN3) {
  STAT(1);
  float fx = (x - w->ox) * w->inv, fz = (z - w->oz) * w->inv;
  if (!(fx >= 0.f && fz >= 0.f)) return 0;
  int gx = (int)fx, gz = (int)fz;
  if (gx >= w->W || gz >= w->H) return 0;
  uint32_t c = (uint32_t)gz * (uint32_t)w->W + (uint32_t)gx;
  const uint32_t *r = w->refs + w->cellStart[c], *e = w->refs + w->cellStart[c + 1];
  float best = -3.0e38f, bn0 = 0, bn1 = 1, bn2 = 0; int found = 0;
  for (; r < e; r++) {
    uint32_t t = *r >> 29, i = *r & 0x1fffffffu;
    if (t == COL_TRI) {
      const ColTri *T = &w->tri[i];
      if (T->n[1] <= COL_WALK_NY) continue;
      float ax = T->a[0], az = T->a[2], bx = T->b[0], bz = T->b[2], cx = T->c[0], cz = T->c[2];
      // n.y > 0  =>  cross2(b-a, c-a) < 0: внутри все три функции рёбер <= 0 (с запасом TRI_EDGE_EPS * длина ребра)
      float e0x = bx - ax, e0z = bz - az, w0 = e0x * (z - az) - e0z * (x - ax);
      if (w0 > 0 && w0 * w0 > TRI_EDGE_EPS * TRI_EDGE_EPS * (e0x * e0x + e0z * e0z)) continue;
      float e1x = cx - bx, e1z = cz - bz, w1 = e1x * (z - bz) - e1z * (x - bx);
      if (w1 > 0 && w1 * w1 > TRI_EDGE_EPS * TRI_EDGE_EPS * (e1x * e1x + e1z * e1z)) continue;
      float e2x = ax - cx, e2z = az - cz, w2 = e2x * (z - cz) - e2z * (x - cx);
      if (w2 > 0 && w2 * w2 > TRI_EDGE_EPS * TRI_EDGE_EPS * (e2x * e2x + e2z * e2z)) continue;
      float y = T->a[1] - (T->n[0] * (x - ax) + T->n[2] * (z - az)) / T->n[1];
      if (y <= yTop && y >= yBottom && y > best) { best = y; bn0 = T->n[0]; bn1 = T->n[1]; bn2 = T->n[2]; found = 1; }
    } else if (t == COL_BOX) {
      const ColBox *B = &w->box[i];
      const float *A[3] = {B->ax, B->ay, B->az};
      float dx = x - B->c[0], dy = yTop - B->c[1], dz = z - B->c[2];
      float tmin = -3.0e38f, tmax = 3.0e38f; int ek = -1; float es = 0;
      int miss = 0;
      for (int k = 0; k < 3; k++) {
        float lo = dx * A[k][0] + dy * A[k][1] + dz * A[k][2], dd = -A[k][1], hk = B->h[k];
        if (fabsf(dd) < 1e-7f) { if (lo < -hk || lo > hk) { miss = 1; break; } continue; }
        float t1 = (-hk - lo) / dd, t2 = (hk - lo) / dd, sg = -1.f;   // вход через грань -h (нормаль -ось), если dd > 0
        if (t1 > t2) { float q = t1; t1 = t2; t2 = q; sg = 1.f; }
        if (t1 > tmin) { tmin = t1; ek = k; es = sg; }
        if (t2 < tmax) tmax = t2;
        if (tmin > tmax) { miss = 1; break; }
      }
      if (miss || ek < 0 || tmin < 0.f) continue;         // мимо / верх выше yTop (начало луча внутри ящика)
      float ny = es * A[ek][1];
      if (ny <= COL_WALK_NY) continue;                      // первой встречается крутая грань — стоять нельзя
      float y = yTop - tmin;
      if (y >= yBottom && y > best) { best = y; bn0 = es * A[ek][0]; bn1 = ny; bn2 = es * A[ek][2]; found = 1; }
    } else if (t == COL_CYL) {
      const ColCyl *C = &w->cyl[i];
      float rc = C->r, hl = C->halfLen, dx = x - C->c[0], dz = z - C->c[2];
      float axz = sqrtf(C->axis[0] * C->axis[0] + C->axis[2] * C->axis[2]), rr = rc + hl * axz;
      if (dx * dx + dz * dz > rr * rr) continue;
      float y, n0, n1, n2;
      if (fabsf(C->axis[1]) > 0.999f || hl <= 0.f) {         // вертикальный цилиндр/капсула или сфера
        float d2 = dx * dx + dz * dz; if (d2 > rc * rc) continue;
        float top = C->c[1] + hl * fabsf(C->axis[1]);
        if (C->flat && hl > 0.f) { y = top; n0 = 0; n1 = 1; n2 = 0; }
        else { float hh = sqrtf(rc * rc - d2); y = top + hh; n0 = dx / rc; n1 = hh / rc; n2 = dz / rc; }
      } else {                                               // наклонная капсула (наклонный плоский цилиндр — как капсула)
        float pax = C->c[0] - C->axis[0] * hl, pay = C->c[1] - C->axis[1] * hl, paz = C->c[2] - C->axis[2] * hl;
        float bax = 2 * hl * C->axis[0], bay = 2 * hl * C->axis[1], baz = 2 * hl * C->axis[2];
        float oax = x - pax, oay = yTop - pay, oaz = z - paz;   // луч: o + t * (0,-1,0)
        float baba = bax * bax + bay * bay + baz * baz, bard = -bay, baoa = bax * oax + bay * oay + baz * oaz;
        float rdoa = -oay, oaoa = oax * oax + oay * oay + oaz * oaz;
        float qa = baba - bard * bard, qb = baba * rdoa - baoa * bard, qc = baba * oaoa - baoa * baoa - rc * rc * baba;
        float hh = qb * qb - qa * qc; if (hh < 0.f || qa <= 0.f) continue;
        float tt = (-qb - sqrtf(hh)) / qa, yy = baoa + tt * bard;
        if (!(yy > 0.f && yy < baba)) {
          float ocx = yy <= 0.f ? oax : x - (pax + bax), ocy = yy <= 0.f ? oay : yTop - (pay + bay), ocz = yy <= 0.f ? oaz : z - (paz + baz);
          float b2 = -ocy, c2 = ocx * ocx + ocy * ocy + ocz * ocz - rc * rc, h2 = b2 * b2 - c2;
          if (h2 <= 0.f) continue;
          tt = -b2 - sqrtf(h2);
        }
        if (tt < 0.f) continue;
        float hx = x, hy = yTop - tt, hz = z;
        float u = ((hx - pax) * bax + (hy - pay) * bay + (hz - paz) * baz) / baba; u = u < 0 ? 0 : u > 1 ? 1 : u;
        n0 = (hx - (pax + bax * u)) / rc; n1 = (hy - (pay + bay * u)) / rc; n2 = (hz - (paz + baz * u)) / rc;
        if (n1 <= COL_WALK_NY) continue;
        y = hy;
      }
      if (n1 <= COL_WALK_NY) continue;
      if (y <= yTop && y >= yBottom && y > best) { best = y; bn0 = n0; bn1 = n1; bn2 = n2; found = 1; }
    }
  }
  if (found) { if (outY) *outY = best; if (outN3) { outN3[0] = bn0; outN3[1] = bn1; outN3[2] = bn2; } }
  return found;
}

// ---------------------------------------------------------------------------------------------- кузов: фигуры
typedef struct { float x, z, s; } P3;   // точка: xz + высота над полом (s)

static void addAxis(Shape *sh, float ux, float uz) {
  float l = ux * ux + uz * uz;
  if (l < 1e-10f || sh->na >= MAXA) return;
  l = 1.f / sqrtf(l); ux *= l; uz *= l;
  for (int k = 0; k < sh->na; k++) if (fabsf(sh->a[k][0] * uz - sh->a[k][1] * ux) < 1e-4f) return;   // параллельна
  sh->a[sh->na][0] = ux; sh->a[sh->na][1] = uz; sh->na++;
}
static int clipS(const P3 *in, int n, P3 *out, float bound, int keepAbove) {
  int m = 0;
  for (int i = 0; i < n; i++) {
    const P3 *c = &in[i], *p = &in[(i + n - 1) % n];
    int ci = keepAbove ? c->s >= bound : c->s <= bound, pi = keepAbove ? p->s >= bound : p->s <= bound;
    if (ci != pi) {
      float t = (bound - p->s) / (c->s - p->s);
      out[m].x = p->x + (c->x - p->x) * t; out[m].z = p->z + (c->z - p->z) * t; out[m].s = bound; m++;
    }
    if (ci) out[m++] = *c;
  }
  return m;
}

typedef struct { float cx, cz, y, gx, gz, lo, hi, x0, z0, x1, z1, ylo, yhi; } Q;   // запрос: пол, слой, габарит
static float slabS(const Q *q, float x, float y, float z) { return y - q->y - q->gx * (x - q->cx) - q->gz * (z - q->cz); }

static int sliceTri(const Q *q, const ColTri *T, Shape *sh) {
  P3 a[3] = {{T->a[0], T->a[2], slabS(q, T->a[0], T->a[1], T->a[2])},
             {T->b[0], T->b[2], slabS(q, T->b[0], T->b[1], T->b[2])},
             {T->c[0], T->c[2], slabS(q, T->c[0], T->c[1], T->c[2])}};
  P3 b[5], c[6];
  float smin = fminf_(a[0].s, fminf_(a[1].s, a[2].s)), smax = fmaxf_(a[0].s, fmaxf_(a[1].s, a[2].s));
  if (smax < q->lo + GRAZE || smin > q->hi - GRAZE) return 0;
  int n = clipS(a, 3, b, q->lo, 1); if (!n) return 0;
  n = clipS(b, n, c, q->hi, 0); if (!n) return 0;
  sh->kind = SH_CONVEX; sh->rad = 0; sh->np = 0; sh->na = 0;
  for (int i = 0; i < n; i++) { sh->p[sh->np][0] = c[i].x; sh->p[sh->np][1] = c[i].z; sh->np++; }
  for (int i = 0; i < n; i++) {
    int j = (i + 1) % n; float ex = c[j].x - c[i].x, ez = c[j].z - c[i].z;
    if (ex * ex + ez * ez > 1e-8f) addAxis(sh, -ez, ex);
  }
  if (!sh->na) {   // срез выродился в точку по xz (вертикальное ребро) — ось по нормали треугольника
    addAxis(sh, T->n[0], T->n[2]); if (!sh->na) addAxis(sh, 1, 0);
  }
  return 1;
}

static int sliceBox(const Q *q, const ColBox *B, Shape *sh) {
  float P[8][3], S[8];
  for (int i = 0; i < 8; i++) {
    float sx = (i & 1) ? B->h[0] : -B->h[0], sy = (i & 2) ? B->h[1] : -B->h[1], sz = (i & 4) ? B->h[2] : -B->h[2];
    for (int k = 0; k < 3; k++) P[i][k] = B->c[k] + B->ax[k] * sx + B->ay[k] * sy + B->az[k] * sz;
    S[i] = slabS(q, P[i][0], P[i][1], P[i][2]);
  }
  float smin = S[0], smax = S[0];
  for (int i = 1; i < 8; i++) { smin = fminf_(smin, S[i]); smax = fmaxf_(smax, S[i]); }
  if (smax < q->lo + GRAZE || smin > q->hi - GRAZE) return 0;
  sh->kind = SH_CONVEX; sh->rad = 0; sh->np = 0; sh->na = 0;
  for (int i = 0; i < 8; i++)
    if (S[i] >= q->lo && S[i] <= q->hi) { sh->p[sh->np][0] = P[i][0]; sh->p[sh->np][1] = P[i][2]; sh->np++; }
  for (int bit = 1; bit < 8; bit <<= 1)
    for (int i = 0; i < 8; i++) {
      if (i & bit) continue;
      int j = i | bit;
      for (int pl = 0; pl < 2; pl++) {
        float b = pl ? q->hi : q->lo, di = S[i] - b, dj = S[j] - b;
        if ((di < 0) == (dj < 0)) continue;
        float t = di / (di - dj);
        if (sh->np < MAXP) {
          sh->p[sh->np][0] = P[i][0] + (P[j][0] - P[i][0]) * t; sh->p[sh->np][1] = P[i][2] + (P[j][2] - P[i][2]) * t; sh->np++;
        }
      }
    }
  if (!sh->np) return 0;
  const float *A[3] = {B->ax, B->ay, B->az};
  for (int k = 0; k < 3; k++) {
    const float *e = A[k];
    addAxis(sh, -e[2], e[0]);                                    // рёбра ящика вдоль e
    float cx = -e[1] * q->gz - e[2], cz = e[0] + e[1] * q->gx;   // линия грани (нормаль e) на плоскости слоя
    addAxis(sh, -cz, cx);
  }
  if (!sh->na) addAxis(sh, 1, 0);
  return 1;
}

static int sliceCyl(const Q *q, const ColCyl *C, Shape *sh) {
  float hl = C->halfLen, r = C->r;
  float p0x = C->c[0] - C->axis[0] * hl, p0y = C->c[1] - C->axis[1] * hl, p0z = C->c[2] - C->axis[2] * hl;
  float p1x = C->c[0] + C->axis[0] * hl, p1y = C->c[1] + C->axis[1] * hl, p1z = C->c[2] + C->axis[2] * hl;
  float s0 = slabS(q, p0x, p0y, p0z), s1 = slabS(q, p1x, p1y, p1z);
  float g2 = q->gx * q->gx + q->gz * q->gz, kN = sqrtf(1.f + g2), gs = sqrtf(g2);
  float smin = fminf_(s0, s1), smax = fmaxf_(s0, s1), L, U, rad;
  if (C->flat && hl > 0.f && fabsf(C->axis[1]) > 0.99f) {       // вертикальный цилиндр с плоскими торцами
    L = q->lo - r * gs; U = q->hi + r * gs;
    if (smax < L + GRAZE || smin > U - GRAZE) return 0;
    rad = r;
  } else {                                                       // капсула / сфера / наклонный (как капсула)
    float gap = fmaxf_(0.f, fmaxf_(q->lo - smax, smin - q->hi)) / kN;
    if (gap >= r - GRAZE) return 0;
    rad = sqrtf(r * r - gap * gap);
    L = q->lo - r * kN; U = q->hi + r * kN;
  }
  float ta = 0.f, tb = 1.f, ds = s1 - s0;
  if (fabsf(ds) > 1e-6f) {
    float u0 = (L - s0) / ds, u1 = (U - s0) / ds;
    if (u0 > u1) { float t = u0; u0 = u1; u1 = t; }
    ta = fmaxf_(0.f, u0); tb = fminf_(1.f, u1);
    if (ta > tb) return 0;
  }
  sh->kind = SH_CONVEX; sh->rad = rad; sh->np = 0; sh->na = 0;
  float ax_ = p0x + (p1x - p0x) * ta, az_ = p0z + (p1z - p0z) * ta, bx_ = p0x + (p1x - p0x) * tb, bz_ = p0z + (p1z - p0z) * tb;
  sh->p[0][0] = ax_; sh->p[0][1] = az_; sh->np = 1;
  float ex = bx_ - ax_, ez = bz_ - az_;
  if (ex * ex + ez * ez > 1e-8f) { sh->p[1][0] = bx_; sh->p[1][1] = bz_; sh->np = 2; addAxis(sh, -ez, ex); }
  return 1;
}

// широкая фаза + срезы: собрать фигуры всего, что может задеть кузов
static int gather(const ColWorld *w, const CarBox *b, Q *q) {
  ColScratch *S = w->scr; STAT(0);
  float fx = b->fx, fz = b->fz, rx = -fz, rz = fx;
  float ex = fabsf(fx) * b->hl + fabsf(rx) * b->hw + GATHER_MARGIN, ez = fabsf(fz) * b->hl + fabsf(rz) * b->hw + GATHER_MARGIN;
  q->cx = b->x; q->cz = b->z; q->y = b->y; q->gx = b->gx; q->gz = b->gz; q->lo = b->lo; q->hi = b->hi;
  q->x0 = b->x - ex; q->x1 = b->x + ex; q->z0 = b->z - ez; q->z1 = b->z + ez;
  float sl = fabsf(b->gx) * ex + fabsf(b->gz) * ez;
  q->ylo = b->y + b->lo - sl; q->yhi = b->y + b->hi + sl;
  int gx0 = (int)floorf((q->x0 - w->ox) * w->inv), gx1 = (int)floorf((q->x1 - w->ox) * w->inv);
  int gz0 = (int)floorf((q->z0 - w->oz) * w->inv), gz1 = (int)floorf((q->z1 - w->oz) * w->inv);
  if (gx0 < 0) gx0 = 0;
  if (gz0 < 0) gz0 = 0;
  if (gx1 >= w->W) gx1 = w->W - 1;
  if (gz1 >= w->H) gz1 = w->H - 1;
  S->nshape = 0;
  if (gx0 > gx1 || gz0 > gz1) return 0;
  uint32_t o1 = w->ntri, o2 = o1 + w->nbox, o3 = o2 + w->ncyl, nprim = o3 + w->nseg;
  uint16_t st = nextStamp(S, nprim);
  for (int gz = gz0; gz <= gz1; gz++)
    for (int gx = gx0; gx <= gx1; gx++) {
      uint32_t c = (uint32_t)gz * (uint32_t)w->W + (uint32_t)gx;
      for (uint32_t k = w->cellStart[c]; k < w->cellStart[c + 1]; k++) {
        uint32_t t = w->refs[k] >> 29, i = w->refs[k] & 0x1fffffffu;
        uint32_t gid = t == 0 ? i : t == 1 ? o1 + i : t == 2 ? o2 + i : o3 + i;
        if (t == COL_TRI) {                         // проходимую землю не берём вовсе (по биту, не читая треугольник)
          if (!(S->steep[i >> 3] & (1u << (i & 7)))) continue;
          const ColTri *T = &w->tri[i];
          if (S->stamp[gid] == st) continue;
          S->stamp[gid] = st;
          float mnx = fminf_(T->a[0], fminf_(T->b[0], T->c[0])), mxx = fmaxf_(T->a[0], fmaxf_(T->b[0], T->c[0]));
          float mnz = fminf_(T->a[2], fminf_(T->b[2], T->c[2])), mxz = fmaxf_(T->a[2], fmaxf_(T->b[2], T->c[2]));
          float mny = fminf_(T->a[1], fminf_(T->b[1], T->c[1])), mxy = fmaxf_(T->a[1], fmaxf_(T->b[1], T->c[1]));
          if (mxx < q->x0 || mnx > q->x1 || mxz < q->z0 || mnz > q->z1 || mxy < q->ylo || mny > q->yhi) continue;
          if (S->nshape >= MAXSHAPE) continue;
          Shape *sh = &S->shape[S->nshape];
          if (sliceTri(q, T, sh)) { sh->ptype = COL_TRI; sh->idx = i; S->nshape++; }
        } else {
          if (S->stamp[gid] == st) continue;
          S->stamp[gid] = st;
          if (S->nshape >= MAXSHAPE) continue;
          Shape *sh = &S->shape[S->nshape];
          if (t == COL_BOX) {
            const ColBox *B = &w->box[i];
            float hx = fabsf(B->ax[0]) * B->h[0] + fabsf(B->ay[0]) * B->h[1] + fabsf(B->az[0]) * B->h[2];
            float hy = fabsf(B->ax[1]) * B->h[0] + fabsf(B->ay[1]) * B->h[1] + fabsf(B->az[1]) * B->h[2];
            float hz = fabsf(B->ax[2]) * B->h[0] + fabsf(B->ay[2]) * B->h[1] + fabsf(B->az[2]) * B->h[2];
            if (B->c[0] + hx < q->x0 || B->c[0] - hx > q->x1 || B->c[2] + hz < q->z0 || B->c[2] - hz > q->z1 ||
                B->c[1] + hy < q->ylo || B->c[1] - hy > q->yhi) continue;
            if (sliceBox(q, B, sh)) { sh->ptype = COL_BOX; sh->idx = i; S->nshape++; }
          } else if (t == COL_CYL) {
            const ColCyl *C = &w->cyl[i];
            float hx = fabsf(C->axis[0]) * C->halfLen + C->r, hy = fabsf(C->axis[1]) * C->halfLen + C->r;
            float hz = fabsf(C->axis[2]) * C->halfLen + C->r;
            if (C->c[0] + hx < q->x0 || C->c[0] - hx > q->x1 || C->c[2] + hz < q->z0 || C->c[2] - hz > q->z1 ||
                C->c[1] + hy < q->ylo || C->c[1] - hy > q->yhi) continue;
            if (sliceCyl(q, C, sh)) { sh->ptype = COL_CYL; sh->idx = i; S->nshape++; }
          } else {
            const ColSeg *G = &w->seg[i];
            if (G->y1 < q->ylo || G->y0 > q->yhi) continue;
            float mnx = fminf_(G->a[0], G->b[0]), mxx = fmaxf_(G->a[0], G->b[0]);
            float mnz = fminf_(G->a[1], G->b[1]), mxz = fmaxf_(G->a[1], G->b[1]);
            if (mxx < q->x0 || mnx > q->x1 || mxz < q->z0 || mnz > q->z1) continue;
            float dx = G->b[0] - G->a[0], dz = G->b[1] - G->a[1], L = sqrtf(dx * dx + dz * dz);
            if (L < 1e-4f) continue;
            uint8_t f = S->segFlags[i];
            sh->kind = SH_FENCE; sh->ptype = COL_SEG; sh->idx = i; sh->np = sh->na = 0; sh->rad = 0;
            sh->fa[0] = G->a[0]; sh->fa[1] = G->a[1]; sh->fd[0] = dx / L; sh->fd[1] = dz / L;
            sh->fn[0] = G->n[0]; sh->fn[1] = G->n[1]; sh->L = L;
            sh->t0 = (f & SF_EXT_A) ? -FENCE_EXT : 0.f; sh->t1 = L + ((f & SF_EXT_B) ? FENCE_EXT : 0.f);
            sh->fflags = f;
            S->nshape++;
          }
        }
      }
    }
  return S->nshape;
}

// ---------------------------------------------------------------------------------------------- кузов: SAT
typedef struct { float cx, cz, fx, fz, rx, rz, hw, hl; } Rect;

// глубина проникновения фигуры в прямоугольник и направление, куда толкать машину (0 = не пересекаются)
static float evalShape(const Shape *s, const Rect *R, float *dx, float *dz, int *behind) {
  *behind = 0;
  if (s->kind == SH_FENCE) {
    // координаты забора: t вдоль (fd), u по нормали (fn). Забор — прямоугольник t в [t0, t1], u в [-FENCE_D, 0]
    // (центр кузова с изнанки в пределах отрезка — зеркально: u в [0, FENCE_D], толкаем дальше на изнанку)
    float ox = R->cx - s->fa[0], oz = R->cz - s->fa[1];
    float ct = ox * s->fd[0] + oz * s->fd[1], cu = ox * s->fn[0] + oz * s->fn[1];
    float ft = R->fx * s->fd[0] + R->fz * s->fd[1], fu = R->fx * s->fn[0] + R->fz * s->fn[1];
    float rt = R->rx * s->fd[0] + R->rz * s->fd[1], ru = R->rx * s->fn[0] + R->rz * s->fn[1];
    int back = cu < 0.f && ct >= 0.f && ct <= s->L;
    float sn = back ? -1.f : 1.f, u0 = back ? 0.f : -FENCE_D, u1 = back ? FENCE_D : 0.f;
    float qt = (s->t0 + s->t1) * .5f, qu = (u0 + u1) * .5f, ht = (s->t1 - s->t0) * .5f, hu = FENCE_D * .5f;
    float ax[4][2] = {{0.f, 1.f}, {1.f, 0.f}, {ft, fu}, {rt, ru}};
    float best = 3.0e38f, pt_ = 0, pu_ = 0;
    for (int k = 0; k < 4; k++) {
      float at = ax[k][0], au = ax[k][1];
      float qc = qt * at + qu * au, qe = ht * fabsf(at) + hu * fabsf(au);
      float rc = ct * at + cu * au, re = R->hl * fabsf(ft * at + fu * au) + R->hw * fabsf(rt * at + ru * au);
      float o1 = (qc + qe) - (rc - re), o2 = (rc + re) - (qc - qe);   // o1: толкать +ось, o2: -ось
      if (o1 <= 0.f || o2 <= 0.f) return 0.f;
      for (int sg = 0; sg < 2; sg++) {
        float o = sg ? o2 : o1, dt_ = sg ? -at : at, du_ = sg ? -au : au;
        if (o >= best) continue;
        if (du_ * sn < -0.01f) continue;                                  // на изнанку — нельзя
        if (dt_ < -0.01f && !(s->fflags & SF_CVX_A)) continue;            // за начало — только если там выпуклый угол
        if (dt_ > 0.01f && !(s->fflags & SF_CVX_B)) continue;             // за конец — так же
        best = o; pt_ = dt_; pu_ = du_;
      }
    }
    if (best > 1e30f) { best = 0.f; }
    *dx = pt_ * s->fd[0] + pu_ * s->fn[0]; *dz = pt_ * s->fd[1] + pu_ * s->fn[1];
    *behind = back;
    return best;
  }
  // выпуклая фигура (+ радиус): SAT по осям прямоугольника, фигуры и (для скруглённых) от угла прямоугольника к точке
  float best = 3.0e38f, bx = 0, bz = 0;
  const float rad = s->rad;
#define SAT_AXIS(UX, UZ) do { \
    float ux_ = (UX), uz_ = (UZ); \
    float ru_ = R->hl * fabsf(R->fx * ux_ + R->fz * uz_) + R->hw * fabsf(R->rx * ux_ + R->rz * uz_); \
    float mn_ = 3.0e38f, mx_ = -3.0e38f; \
    for (int k_ = 0; k_ < s->np; k_++) { \
      float d_ = (s->p[k_][0] - R->cx) * ux_ + (s->p[k_][1] - R->cz) * uz_; \
      mn_ = d_ < mn_ ? d_ : mn_; mx_ = d_ > mx_ ? d_ : mx_; } \
    mn_ -= rad; mx_ += rad; \
    float o1_ = mx_ + ru_; if (o1_ <= 0.f) return 0.f; \
    float o2_ = ru_ - mn_; if (o2_ <= 0.f) return 0.f; \
    if (o1_ < o2_) { if (o1_ < best) { best = o1_; bx = ux_; bz = uz_; } } \
    else if (o2_ < best) { best = o2_; bx = -ux_; bz = -uz_; } \
  } while (0)
  SAT_AXIS(R->fx, R->fz);
  SAT_AXIS(R->rx, R->rz);
  for (int k = 0; k < s->na; k++) SAT_AXIS(s->a[k][0], s->a[k][1]);
  if (rad > 0.f)
    for (int k = 0; k < s->np; k++) {
      float px = s->p[k][0] - R->cx, pz = s->p[k][1] - R->cz;
      float lf = px * R->fx + pz * R->fz, lr = px * R->rx + pz * R->rz;
      float cf = lf < -R->hl ? -R->hl : lf > R->hl ? R->hl : lf, cr = lr < -R->hw ? -R->hw : lr > R->hw ? R->hw : lr;
      if (cf == lf && cr == lr) continue;                // точка внутри — хватит других осей
      float vx = px - (R->fx * cf + R->rx * cr), vz = pz - (R->fz * cf + R->rz * cr), l = vx * vx + vz * vz;
      if (l < 1e-12f) continue;
      l = 1.f / sqrtf(l);
      SAT_AXIS(vx * l, vz * l);
    }
#undef SAT_AXIS
  // o1 = mx + ru: фигура ниже по оси — машину толкаем по +u; o2 = ru - mn: фигура выше — по -u. (bx, bz) — куда толкать
  *dx = bx; *dz = bz;
  return best;
}

static void rectOf(const CarBox *b, Rect *R) {
  R->cx = b->x; R->cz = b->z; R->fx = b->fx; R->fz = b->fz; R->rx = -b->fz; R->rz = b->fx; R->hw = b->hw; R->hl = b->hl;
}

static void addContact(CarBox *b, const Shape *s, float nx, float nz, float d) {
  for (int k = 0; k < b->n; k++)
    if (b->type[k] == s->ptype && b->nx[k] == nx && b->nz[k] == nz) { b->depth[k] += d; return; }
  if (b->n < COL_MAX_CONTACTS) { b->nx[b->n] = nx; b->nz[b->n] = nz; b->depth[b->n] = d; b->type[b->n] = s->ptype; b->n++; }
  else {   // места нет — заменить самый мелкий
    int m = 0; for (int k = 1; k < b->n; k++) if (b->depth[k] < b->depth[m]) m = k;
    if (d > b->depth[m]) { b->nx[m] = nx; b->nz[m] = nz; b->depth[m] = d; b->type[m] = s->ptype; }
  }
}

int colPushCar(const ColWorld *w, CarBox *b, float *mtvX, float *mtvZ, float *nX, float *nZ) {
  Q q; int ns = gather(w, b, &q);
  const Shape *sh = w->scr->shape;
  float x0 = b->x, z0 = b->z, bestD = 0, bnx = 0, bnz = 0;
  b->n = 0; b->behindFence = 0; b->maxDepth = 0; b->nshapes = ns;
  int it = 0, clean = 0;
  float minD = 3.0e38f, minX = b->x, minZ = b->z;        // положение с наименьшим худшим проникновением
  for (; it < MAX_ITER && ns; it++) {
    Rect R; rectOf(b, &R); STAT(3);
    int bi = -1, bbeh = 0; float bd = PUSH_EPS, bdx = 0, bdz = 0;
    for (int i = 0; i < ns; i++) {
      float dx, dz; int beh;
      float d = evalShape(&sh[i], &R, &dx, &dz, &beh);
      if (d > bd) { bd = d; bi = i; bdx = dx; bdz = dz; bbeh = beh; }
    }
    if (bd < minD) { minD = bd; minX = b->x; minZ = b->z; }
#ifdef COL_DEBUG
    if (colDebug) {
      printf("iter %d: centre %.4f %.4f\n", it, b->x, b->z);
      for (int i = 0; i < ns; i++) { float dx, dz; int beh; float d = evalShape(&sh[i], &R, &dx, &dz, &beh);
        printf("   shape %2d kind %d type %d idx %u np %d na %d rad %.2f: depth %.4f dir %+.3f %+.3f%s\n", i, sh[i].kind, sh[i].ptype, sh[i].idx,
               sh[i].np, sh[i].na, sh[i].rad, d, dx, dz, i == bi ? "  <== push" : ""); }
    }
#endif
    if (bi < 0) { clean = 1; break; }
    if (it >= 3) bd *= .5f;   // зажат с двух сторон — полшага: сходимся к равным проникновениям, а не качаемся
    b->x += bdx * bd; b->z += bdz * bd;
    if (bbeh) b->behindFence = 1;
    addContact(b, &sh[bi], bdx, bdz, bd);
    if (bd > bestD) { bestD = bd; bnx = bdx; bnz = bdz; }
  }
  if (!clean && ns) {   // итерации кончились (зажат с двух сторон): лучшее из пройденных положений
    Rect R; rectOf(b, &R);
    float d = 0.f;
    for (int i = 0; i < ns; i++) {
      float dx, dz; int beh; float e = evalShape(&sh[i], &R, &dx, &dz, &beh);
      if (e > d) d = e;
    }
    if (minD < d) { b->x = minX; b->z = minZ; d = minD; }
    b->maxDepth = d;
  }
  if (mtvX) *mtvX = b->x - x0;
  if (mtvZ) *mtvZ = b->z - z0;
  if (nX) *nX = bnx;
  if (nZ) *nZ = bnz;
  return b->n;
}

int colProbeCar(const ColWorld *w, CarBox *b) {
  Q q; int ns = gather(w, b, &q);
  const Shape *sh = w->scr->shape;
  Rect R; rectOf(b, &R);
  b->n = 0; b->behindFence = 0; b->maxDepth = 0; b->nshapes = ns;
  for (int i = 0; i < ns; i++) {
    float dx, dz; int beh; float d = evalShape(&sh[i], &R, &dx, &dz, &beh);
    if (d > PUSH_EPS) {
      addContact(b, &sh[i], dx, dz, d);
      if (d > b->maxDepth) b->maxDepth = d;
      if (beh) b->behindFence = 1;
    }
  }
  return b->n;
}

int colCrossFence(const ColWorld *w, float x0, float z0, float x1, float z1, float *nX, float *nZ) {
  STAT(2);
  ColScratch *S = w->scr;
  int gx0 = (int)floorf((fminf_(x0, x1) - 0.1f - w->ox) * w->inv), gx1 = (int)floorf((fmaxf_(x0, x1) + 0.1f - w->ox) * w->inv);
  int gz0 = (int)floorf((fminf_(z0, z1) - 0.1f - w->oz) * w->inv), gz1 = (int)floorf((fmaxf_(z0, z1) + 0.1f - w->oz) * w->inv);
  if (gx0 < 0) gx0 = 0;
  if (gz0 < 0) gz0 = 0;
  if (gx1 >= w->W) gx1 = w->W - 1;
  if (gz1 >= w->H) gz1 = w->H - 1;
  if (gx0 > gx1 || gz0 > gz1) return 0;
  uint32_t o3 = w->ntri + w->nbox + w->ncyl, nprim = o3 + w->nseg;
  uint16_t st = nextStamp(S, nprim);
  for (int gz = gz0; gz <= gz1; gz++)
    for (int gx = gx0; gx <= gx1; gx++) {
      uint32_t c = (uint32_t)gz * (uint32_t)w->W + (uint32_t)gx;
      uint32_t k = w->cellStart[c + 1];
      while (k > w->cellStart[c] && (w->refs[k - 1] >> 29) == COL_SEG) k--;   // заборы — в конце списка клетки
      for (; k < w->cellStart[c + 1]; k++) {
        uint32_t i = w->refs[k] & 0x1fffffffu;
        if (S->stamp[o3 + i] == st) continue;
        S->stamp[o3 + i] = st;
        const ColSeg *G = &w->seg[i];
        float s0 = (x0 - G->a[0]) * G->n[0] + (z0 - G->a[1]) * G->n[1];
        float s1 = (x1 - G->a[0]) * G->n[0] + (z1 - G->a[1]) * G->n[1];
        if (!(s0 >= 0.f && s1 < 0.f)) continue;
        float t = s0 / (s0 - s1), px = x0 + (x1 - x0) * t - G->a[0], pz = z0 + (z1 - z0) * t - G->a[1];
        float dx = G->b[0] - G->a[0], dz = G->b[1] - G->a[1], L2 = dx * dx + dz * dz;
        float u = px * dx + pz * dz;
        if (u < 0.f || u > L2) continue;
        if (nX) *nX = G->n[0];
        if (nZ) *nZ = G->n[1];
        return 1;
      }
    }
  return 0;
}
