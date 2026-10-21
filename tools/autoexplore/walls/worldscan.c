// worldscan — детекторы мира автоисследователя, полоса Стены (задание «Автоисследователь» 11.10): офлайн-проход по всей сетке уровня, без бота и без кадров.
// Сравнивает коллизию COL1 с рисуемой геометрией города (кусты и стекло — отдельно) и пишет находки в формате общего интерфейса:
//   level \t x \t y \t z \t type \t weight \t seed \t frame \t description      (в режиме данных seed = 0, frame = 0)
// Типы (словарь Физики): invisible_wall — коллизия держит там, где по лучу нет рисуемой геометрии («не видно, но держит»);
//   pass_through — видимая стена без коллизии в полосе кузова 0,45–1,5 м над полом («видно, но проезжается»);
//   hole — нарисованная земля без опоры коллизии (машина провалится) и, отдельно, опора без нарисованной земли;
//   void_edge — кромка опоры без стенки и без зоны DEATH: за ней пустота или обрыв глубже 4 м (машина съезжает за мир);
//   ground_offset — нарисованная земля выше или ниже опоры коллизии больше чем на 0,15 м (машина и тень едут под видимой землёй или над ней);
//   embedded — точка опоры, где кузов в стене больше 0,3 м при любом из 8 курсов (застрять внутри объекта).
// Повтор: tools/autoexplore/walls/RUN.txt (mode=data: один раз на уровень).
//   cc -std=c11 -O2 -I viewer tools/autoexplore/walls/worldscan.c viewer/col.c viewer/car.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o build/tmp/worldscan
//   worldscan LEVEL.shr LEVEL_NO OUT.tsv [--detectors inv,pass,hole,edge,embed]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <stdarg.h>

unsigned homerSolidFrame;   // заглушка: props.c ссылается на счётчик homer.c, дома он нужен только внутри homerUpdate
#include "scene.h"
static int inDeathXZ(float x, float y, float z) {
  for (uint32_t i = 0; i < W.ndeath; i++) { const ColZone *v = (const ColZone *)&W.death[i]; if (colZoneContains(v, x, v->c[1], z, 1.5f)) return 1; }
  (void)y; return 0;
}
static int ground(float x, float z, float top, float bot, float *y) { float n[3]; return colGround(&W, x, z, top, bot, y, n); }

// ---------------------------------------------------------------- находки и склейка
typedef struct { float x, y, z, w; int n; char type[16]; char desc[200]; } Fnd;
static Fnd *F; static unsigned nF, capF;
static void add(const char *type, float x, float y, float z, float w, const char *fmt, ...) {
  char desc[200]; va_list ap; va_start(ap, fmt); vsnprintf(desc, sizeof desc, fmt, ap); va_end(ap);
  if (nF == capF) { capF = capF ? capF * 2 : 4096; F = realloc(F, capF * sizeof *F); }
  Fnd *f = &F[nF++]; f->x = x; f->y = y; f->z = z; f->w = w; f->n = 1; snprintf(f->type, sizeof f->type, "%s", type); snprintf(f->desc, sizeof f->desc, "%s", desc);
}
static int cmpF(const void *a, const void *b) {
  const Fnd *p = a, *q = b; int c = strcmp(p->type, q->type); if (c) return c;
  int px = (int)floorf(p->x / 4.f), qx = (int)floorf(q->x / 4.f); if (px != qx) return px < qx ? -1 : 1;
  int pz = (int)floorf(p->z / 4.f), qz = (int)floorf(q->z / 4.f); return pz < qz ? -1 : pz > qz;
}

// ---------------------------------------------------------------- 1. «не видно, но держит»
// грань стены (центр P, наружная нормаль N в xz): есть ли рисуемое в 1,2 м вокруг — луч наружу→внутрь и внутрь→наружу
static int faceVisible(const float P[3], const float N[2]) {
  float o[3] = {P[0] + N[0] * .6f, P[1], P[2] + N[1] * .6f}, d[3] = {-N[0], 0, -N[1]};
  if (rayCast(o, d, 1.4f, 0) >= 0) return 1;
  float o2[3] = {P[0] - N[0] * .6f, P[1], P[2] - N[1] * .6f}, d2[3] = {N[0], 0, N[1]};
  return rayCast(o2, d2, 1.4f, 0) >= 0;
}
// граница карты: с обеих сторон грани на 5 м нет опоры мира (или только с одной) — невидимая граница по замыслу оригинала
static int borderFace(const float P[3], const float N[2]) {
  float y; int a = ground(P[0] + N[0] * 5.f, P[2] + N[1] * 5.f, P[1] + 30.f, P[1] - 80.f, &y), b = ground(P[0] - N[0] * 5.f, P[2] - N[1] * 5.f, P[1] + 30.f, P[1] - 80.f, &y);
  return !(a && b);
}
static void primFaces(int kind, unsigned idx, const char *name) {
  // собираем грани-образцы: центр, нормаль xz, низ и верх над опорой
  float ctr[3], N[2]; int nvis = 0, ntot = 0, nbord = 0; float top = 0, bot = 0, len = 0;
  if (kind == COL_SEG) {
    const ColSeg *s = &W.seg[idx]; float dx = s->b[0] - s->a[0], dz = s->b[1] - s->a[1], L = sqrtf(dx * dx + dz * dz); if (L < 1.f || s->y1 - s->y0 < 0.8f) return;
    N[0] = s->n[0]; N[1] = s->n[1]; len = L; bot = s->y0; top = s->y1;
    int steps = (int)(L / 1.5f) + 1;
    for (int k = 0; k < steps; k++) {
      float u = (k + .5f) / steps; ctr[0] = s->a[0] + dx * u; ctr[2] = s->a[1] + dz * u;
      float gy; if (!ground(ctr[0], ctr[2], s->y1 + 2.f, s->y0 - 6.f, &gy)) gy = s->y0;
      ctr[1] = fminf(fmaxf(gy + 0.9f, s->y0 + .3f), s->y1 - .2f);
      if (nearProp(ctr[0], ctr[1], ctr[2], 3.5f)) continue;
      ntot++; if (borderFace(ctr, N)) { nbord++; } else if (faceVisible(ctr, N)) nvis++;
    }
  } else if (kind == COL_BOX) {
    const ColBox *b = &W.box[idx]; if (b->pad == 1.f) return;   // кусты (материал) — проезд по замыслу
    const float *ax[3] = {b->ax, b->ay, b->az}; int up = 0; for (int k = 1; k < 3; k++) if (fabsf(ax[k][1]) > fabsf(ax[up][1])) up = k;
    if (fabsf(ax[up][1]) < .7f) return;   // наклонные коробки (пандусы) — не стенки
    int h1 = (up + 1) % 3, h2 = (up + 2) % 3; float H = b->h[up]; if (H * 2 < 0.8f) return;
    bot = b->c[1] - H; top = b->c[1] + H;
    for (int fa = 0; fa < 2; fa++) {   // две пары вертикальных граней
      int axi = fa ? h2 : h1, oth = fa ? h1 : h2;
      for (int sgn = -1; sgn <= 1; sgn += 2) {
        float nn = sqrtf(ax[axi][0] * ax[axi][0] + ax[axi][2] * ax[axi][2]); if (nn < .3f) continue;
        N[0] = sgn * ax[axi][0] / nn; N[1] = sgn * ax[axi][2] / nn;
        float fw = b->h[oth] * 2; len += fw; int steps = (int)(fw / 1.5f) + 1;
        for (int k = 0; k < steps; k++) {
          float u = ((k + .5f) / steps - .5f) * 2 * b->h[oth];
          ctr[0] = b->c[0] + sgn * ax[axi][0] * b->h[axi] + ax[oth][0] * u; ctr[2] = b->c[2] + sgn * ax[axi][2] * b->h[axi] + ax[oth][2] * u;
          float gy; if (!ground(ctr[0], ctr[2], top + 2.f, bot - 6.f, &gy)) gy = bot;
          ctr[1] = fminf(fmaxf(gy + 0.9f, bot + .3f), top - .2f);
          if (nearProp(ctr[0], ctr[1], ctr[2], 3.5f)) continue;
          ntot++; if (borderFace(ctr, N)) nbord++; else if (faceVisible(ctr, N)) nvis++;
        }
      }
    }
    ctr[0] = b->c[0]; ctr[1] = b->c[1]; ctr[2] = b->c[2];
  } else return;
  if (ntot < 2) return;
  float cx = 0, cz = 0;
  if (kind == COL_SEG) { const ColSeg *s = &W.seg[idx]; cx = (s->a[0] + s->b[0]) / 2; cz = (s->a[1] + s->b[1]) / 2; ctr[1] = (s->y0 + s->y1) / 2; }
  else { cx = ctr[0]; cz = ctr[2]; }
  float inv = (float)(ntot - nvis - nbord) / ntot;
  if (inv < .8f) return;   // видно хотя бы на пятой части граней
  add("invisible_wall", cx, ctr[1], cz, fminf(10.f, 3.f + len / 8.f + (top - bot) / 4.f), "%s %u: длина граней %.0f м, высота %.1f–%.1f, невидимых граней %d из %d (граница карты %d)", kind == COL_SEG ? "забор" : "коробка", idx, len, bot, top, ntot - nvis - nbord, ntot, nbord);
  (void)name;
}
static void detInvisible(void) {
  for (uint32_t i = 0; i < W.nseg; i++) primFaces(COL_SEG, i, 0);
  for (uint32_t i = 0; i < W.nbox; i++) primFaces(COL_BOX, i, 0);
  // цилиндры (столбы, стволы): вертикальные, радиус ≥ 0.25: 4 образца на мид-высоте
  for (uint32_t i = 0; i < W.ncyl; i++) {
    const ColCyl *c = &W.cyl[i]; if (c->pad[0] == 1.f || fabsf(c->axis[1]) < .7f || c->halfLen * 2 < 0.8f || c->r < .25f) continue;
    float gy; if (!ground(c->c[0], c->c[2], c->c[1] + c->halfLen + 2.f, c->c[1] - c->halfLen - 6.f, &gy)) gy = c->c[1] - c->halfLen;
    float P[3] = {c->c[0], fminf(fmaxf(gy + 0.9f, c->c[1] - c->halfLen + .3f), c->c[1] + c->halfLen - .2f), c->c[2]};
    if (nearProp(P[0], P[1], P[2], 3.5f)) continue;
    int vis = 0; for (int a = 0; a < 4; a++) { float N[2] = {cosf(a * 1.5708f), sinf(a * 1.5708f)}, Q[3] = {P[0] + N[0] * c->r, P[1], P[2] + N[1] * c->r}; vis += faceVisible(Q, N); }
    if (vis == 0) add("invisible_wall", P[0], P[1], P[2], 3.f, "цилиндр %u: r %.1f, высота %.1f, рисуемого вокруг нет", i, c->r, c->halfLen * 2);
  }
}

// ---------------------------------------------------------------- 2. «видно, но проезжается»
static void detPass(void) {
  for (unsigned t = 0; t < NT; t++) {
    if (TF[t]) continue; const float *a = T + 9 * t;
    float e1[3] = {a[3] - a[0], a[4] - a[1], a[5] - a[2]}, e2[3] = {a[6] - a[0], a[7] - a[1], a[8] - a[2]};
    float n[3] = {e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]}, ar = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    if (ar < 2.4f) continue;   // площадь < 1.2 м²
    n[0] /= ar; n[1] /= ar; n[2] /= ar; if (fabsf(n[1]) > .35f) continue;   // не стена
    float hn = sqrtf(n[0] * n[0] + n[2] * n[2]); if (hn < .5f) continue; float N[2] = {n[0] / hn, n[2] / hn};
    float ymin = fminf(a[1], fminf(a[4], a[7])), ymax = fmaxf(a[1], fmaxf(a[4], a[7])); if (ymax - ymin < 0.8f) continue;
    float edge = fmaxf(sqrtf(e1[0] * e1[0] + e1[2] * e1[2]), fmaxf(sqrtf(e2[0] * e2[0] + e2[2] * e2[2]), sqrtf((a[6] - a[3]) * (a[6] - a[3]) + (a[8] - a[5]) * (a[8] - a[5]))));
    int k = (int)(edge / 1.2f) + 1; if (k > 8) k = 8; int ns = 0, nopen = 0; float sx = 0, sy = 0, sz = 0;
    for (int i = 0; i <= k; i++) for (int j = 0; i + j <= k; j++) {
      float u = (i + .33f) / (k + 1), v = (j + .33f) / (k + 1);
      float P[3] = {a[0] + e1[0] * u + e2[0] * v, a[1] + e1[1] * u + e2[1] * v, a[2] + e1[2] * u + e2[2] * v};
      float gy; if (!ground(P[0], P[2], P[1] + 1.f, P[1] - 4.f, &gy)) continue;
      if (P[1] < gy + .35f || P[1] > gy + 1.8f) continue;
      float Y = fminf(fmaxf(P[1], gy + .5f), gy + 1.4f); if (Y < ymin - .05f || Y > ymax + .05f) continue;
      if (nearProp(P[0], P[1], P[2], 3.5f)) continue;
      float p0[3] = {P[0] + N[0] * .8f, Y, P[2] + N[1] * .8f}, p1[3] = {P[0] - N[0] * .8f, Y, P[2] - N[1] * .8f};
      float q0[3] = {p0[0], Y + .5f > gy + 1.5f ? gy + 1.5f : Y + .5f, p0[2]}, q1[3] = {p1[0], q0[1], p1[2]};
      ns++;
      if (colRayFrac(&W, p0, p1, 0) >= 1.f && colRayFrac(&W, q0, q1, 0) >= 1.f) { nopen++; sx += P[0]; sy += Y; sz += P[2]; }
    }
    if (ns >= 2 && nopen >= (ns + 1) / 2 + (ns == 2) && nopen >= 2)
      add("pass_through", sx / nopen, sy / nopen, sz / nopen, fminf(10.f, 2.f + ar / 12.f), "рисуемая стена %.0f м² (высота %.1f–%.1f) без коллизии: образцов %d, открытых %d", ar / 2, ymin, ymax, ns, nopen);
  }
}

// ---------------------------------------------------------------- 3. дыры: земля без опоры и опора без земли
static void detHole(void) {
  for (unsigned t = 0; t < NT; t++) {
    if (TF[t]) continue; const float *a = T + 9 * t;
    float e1[3] = {a[3] - a[0], a[4] - a[1], a[5] - a[2]}, e2[3] = {a[6] - a[0], a[7] - a[1], a[8] - a[2]};
    float n[3] = {e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]}, ar = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    if (ar < 8.f || fabsf(n[1]) < .8f * ar) continue;   // земля: площадь от 4 м² и почти горизонтальная
    float P[3] = {(a[0] + a[3] + a[6]) / 3, (a[1] + a[4] + a[7]) / 3, (a[2] + a[5] + a[8]) / 3}; float y;
    if (nearProp(P[0], P[1], P[2], 3.f) || inDeathXZ(P[0], P[1], P[2])) continue;
    if (!ground(P[0], P[2], P[1] + .6f, P[1] - 1.f, &y) || fabsf(y - P[1]) > 1.2f)
      add("hole", P[0], P[1], P[2], fminf(10.f, 3.f + ar / 40.f), "нарисованная земля %.0f м² без опоры коллизии (машина провалится)", ar / 2);
  }
}

// ---------------------------------------------------------------- 4. кромка без стенки
static void detEdge(void) {
  const float step = 3.f; int gx = (int)(W.W * W.cell / step), gz = (int)(W.H * W.cell / step);
  for (int j = 0; j < gz; j++) for (int i = 0; i < gx; i++) {
    float x = W.ox + (i + .5f) * step, z = W.oz + (j + .5f) * step, y;
    if (!ground(x, z, 300.f, -300.f, &y)) continue;
    static const int DX[4] = {1, 0, -1, 0}, DZ[4] = {0, 1, 0, -1};
    for (int d = 0; d < 4; d++) {
      float nx = x + DX[d] * step, nz = z + DZ[d] * step, ny;
      int has = ground(nx, nz, y + 1.2f, y - 4.f, &ny);   // опора не выше +1.2 и не ниже -4
      if (has) continue;
      int deep = !ground(nx, nz, y + 1.2f, y - 400.f, &ny);   // совсем пусто (а не обрыв до земли ниже)
      float p0[3] = {x, y + .6f, z}, p1[3] = {nx, y + .6f, nz}, p2[3] = {x, y + 1.3f, z}, p3[3] = {nx, y + 1.3f, nz};
      if (colRayFrac(&W, p0, p1, 0) < 1.f || colRayFrac(&W, p2, p3, 0) < 1.f) continue;   // стенка есть
      if (inDeathXZ(nx, y, nz) || inDeathXZ(x, y, z)) continue;
      float cy; if (!deep && ground(nx, nz, y - 4.f, y - 400.f, &cy) && y - cy < 4.f) continue;
      if (nearProp(x, y, z, 3.f)) continue;
      add("void_edge", x + DX[d] * step / 2, y, z + DZ[d] * step / 2, deep ? 4.f : 3.f, "кромка опоры без стенки и без зоны DEATH: %s (%+.0f,%+.0f)", deep ? "за ней пусто до самого низа" : "обрыв глубже 4 м", (float)DX[d], (float)DZ[d]);
    }
  }
}

// ---------------------------------------------------------------- 4б. высота земли: нарисованная против коллизии
// Разбор №522 (тень уходит под землю): на J10-2 L1 нарисованная дорога выше опоры коллизии на 0,25–0,4 м — машина (и тень) едут ниже видимой дороги.
// Образец раз в 3 м по опоре: нарисованная земля (верхняя ходовая поверхность не выше опоры + 0,8 м) минус опора; |Δ| > 0.15 — находка ground_offset
static void detOffset(void) {
  const float step = 3.f; int gx = (int)(W.W * W.cell / step), gz = (int)(W.H * W.cell / step);
  for (int j = 0; j < gz; j++) for (int i = 0; i < gx; i++) {
    float x = W.ox + (i + .5f) * step, z = W.oz + (j + .5f) * step, y, n[3];
    if (!colGround(&W, x, z, 300.f, -300.f, &y, n) || n[1] < .7f) continue;
    if (nearProp(x, y, z, 3.f) || inDeathXZ(x, y, z)) continue;
    float rg = renderGround(x, z, y + .8f, 2.5f); if (rg < -1e8f) continue;
    float d = rg - y; if (fabsf(d) < .15f) continue;
    add("ground_offset", x, y, z, fminf(10.f, 2.f + fabsf(d) * 8.f), "нарисованная земля %s опоры коллизии на %.2f м (опора %.2f, рисунок %.2f)", d > 0 ? "выше" : "ниже", fabsf(d), y, rg);
  }
}

// ---------------------------------------------------------------- 4в. куст держит как стена (№524)
// Твёрдый объём (ящик, цилиндр, капсула, забор без пометки листвы), чья площадь на плане почти целиком закрыта рисуемой ЛИСТВОЙ (текстуры shrub|hedge|bush из
// --foltex, иначе любая альфа), без непрозрачной стены в том же объёме: игрок видит куст, машина упирается. Мягкие объёмы (материал FOLIAGE) и заборы с пометкой не в счёте.
static unsigned char *folSet; static int folMax;   // folSet[i] != 0 — текстура i листва
static void loadFol(const char *path) {
  FILE *f = fopen(path, "r"); if (!f) return; static char buf[1 << 16]; size_t n = fread(buf, 1, sizeof buf - 1, f); buf[n] = 0; fclose(f);
  folSet = calloc(4096, 1); folMax = 4096;
  for (char *c = buf; (c = strchr(c, '"')); ) { c++; char *e; long v = strtol(c, &e, 10); if (e != c && *e == '"' && v >= 0 && v < 4096) folSet[v] = 1; c = strchr(c, '"'); if (!c) break; c++; }
}
static int isFolTri(unsigned t) { return folSet ? (TX[t] >= 0 && TX[t] < folMax && folSet[TX[t]]) : (TF[t] & 1); }
// покрытие точки (x, z) рисуемым в слое y0..y1: 0 пусто, 1 лист, 2 непрозрачное не лист
static int coverAt(float x, float z, float y0, float y1) {
  int cx = (int)floorf((x - GOX) / GC), cz = (int)floorf((z - GOZ) / GC); if (cx < 0 || cz < 0 || cx >= GW || cz >= GH) return 0;
  size_t c = (size_t)cz * GW + cx; int res = 0;
  for (unsigned k = gStart[c]; k < gStart[c + 1]; k++) {
    unsigned t = gList[k]; const float *a = T + 9 * t;
    float d = (a[3] - a[0]) * (a[8] - a[2]) - (a[5] - a[2]) * (a[6] - a[0]); if (fabsf(d) < 1e-9f) continue;
    float u = ((x - a[0]) * (a[8] - a[2]) - (z - a[2]) * (a[6] - a[0])) / d, v = ((a[3] - a[0]) * (z - a[2]) - (a[5] - a[2]) * (x - a[0])) / d;
    if (u < -.02f || v < -.02f || u + v > 1.02f) continue;
    float y = a[1] + u * (a[4] - a[1]) + v * (a[7] - a[1]); if (y < y0 || y > y1) continue;
    if (isFolTri(t)) res = res ? res : 1; else if (!(TF[t] & 3)) return 2; else if (res == 0) res = 1 * 0;   // стекло/смешивание не лист и не стена: пропуск
  }
  return res;
}
static void bushCheck(const char *what, int idx, const float *pts, int np, float ylo, float yhi, float cx, float cy, float cz) {
  int fol = 0, solid = 0, none = 0;
  for (int i = 0; i < np; i++) { int r = coverAt(pts[2 * i], pts[2 * i + 1], ylo - .2f, yhi + .3f); if (r == 1) fol++; else if (r == 2) solid++; else none++; }
  if (fol < 4 || solid * 4 > fol || fol * 2 < np) return;   // листвы мало или есть стена или половина площади пуста
  add("bush_holds", cx, cy, cz, fminf(10.f, 4.f + .15f * fol), "куст держит как стена: %s %d, листвой закрыто %d из %d точек плана, стены %d", what, idx, fol, np, solid);
}
static void detBush(void) {
  for (uint32_t i = 0; i < W.nbox; i++) {
    const ColBox *b = &W.box[i]; if (b->pad > .5f) continue; if (nearProp(b->c[0], b->c[1], b->c[2], 2.f)) continue;
    float pts[2 * 400]; int np = 0; float ymin = 1e9f, ymax = -1e9f;
    for (float a = -1; a <= 1.001f; a += fminf(1.f, .5f / fmaxf(b->h[0], .05f))) for (float c = -1; c <= 1.001f; c += fminf(1.f, .5f / fmaxf(b->h[2], .05f))) for (float e = -1; e <= 1.001f; e += 1.f) {
      float x = b->c[0] + b->ax[0] * b->h[0] * a + b->ay[0] * b->h[1] * e + b->az[0] * b->h[2] * c, y = b->c[1] + b->ax[1] * b->h[0] * a + b->ay[1] * b->h[1] * e + b->az[1] * b->h[2] * c, z = b->c[2] + b->ax[2] * b->h[0] * a + b->ay[2] * b->h[1] * e + b->az[2] * b->h[2] * c;
      if (y < ymin) ymin = y; if (y > ymax) ymax = y; if (np < 400 && e == 0.f) { pts[2 * np] = x; pts[2 * np + 1] = z; np++; }
    }
    if (np < 4 || ymax - ymin > 4.f) continue; bushCheck("ящик", (int)i, pts, np, ymin, ymax, b->c[0], b->c[1], b->c[2]);
  }
  for (uint32_t i = 0; i < W.ncyl; i++) {
    const ColCyl *q = &W.cyl[i]; if (q->pad[0] > .5f || q->pad[0] > 1.5f) continue; if (nearProp(q->c[0], q->c[1], q->c[2], 2.f)) continue;
    float L = q->halfLen + (q->flat ? 0 : q->r), hx = q->axis[0] * L, hz = q->axis[2] * L; float pts[2 * 400]; int np = 0;
    int steps = (int)fminf(60, 2 + 2 * hypotf(hx, hz) / .5f), rs = (int)fminf(6, 1 + q->r / .5f);
    for (int k = 0; k <= steps; k++) for (int j = -rs; j <= rs; j++) { float t = -1 + 2.f * k / steps, off = q->r * j / rs, nl = hypotf(q->axis[0], q->axis[2]); float ux = nl > .01f ? -q->axis[2] / nl : 1, uz = nl > .01f ? q->axis[0] / nl : 0; if (np < 400) { pts[2 * np] = q->c[0] + hx * t + ux * off; pts[2 * np + 1] = q->c[2] + hz * t + uz * off; np++; } }
    float ylo = q->c[1] - fabsf(q->axis[1]) * L - q->r, yhi = q->c[1] + fabsf(q->axis[1]) * L + q->r; if (yhi - ylo > 4.f) continue;   // деревья: ствол выше 4 м — не куст
    bushCheck("цилиндр", (int)i, pts, np, ylo, yhi, q->c[0], q->c[1], q->c[2]);
  }
  for (uint32_t i = 0; i < W.nseg; i++) {
    const ColSeg *q = &W.seg[i]; if (q->y0 < -1.5e6f) continue; float dx = q->b[0] - q->a[0], dz = q->b[1] - q->a[1], len = hypotf(dx, dz); if (len < 1.f) continue;
    float pts[2 * 400]; int np = 0; for (float t = 0; t <= len && np < 200; t += .5f) for (int s = -1; s <= 1 && np < 400; s++) { pts[2 * np] = q->a[0] + dx / len * t + q->n[0] * .3f * s; pts[2 * np + 1] = q->a[1] + dz / len * t + q->n[1] * .3f * s; np++; }
    float y, n[3]; if (!colGround(&W, q->a[0] + dx * .5f, q->a[1] + dz * .5f, 300.f, -300.f, &y, n)) continue;
    bushCheck("забор", (int)i, pts, np, y, fminf(q->y1, y + 3.f), q->a[0] + dx * .5f, y, q->a[1] + dz * .5f);
  }
}

// ---------------------------------------------------------------- 5. внутри объекта
static void detEmbedded(void) {
  const float step = 2.f; int gx = (int)(W.W * W.cell / step), gz = (int)(W.H * W.cell / step);
  for (int j = 0; j < gz; j++) for (int i = 0; i < gx; i++) {
    float x = W.ox + (i + .5f) * step, z = W.oz + (j + .5f) * step, y;
    if (!ground(x, z, 300.f, -300.f, &y)) continue;
    float yy = y; int all = 1; float worst = 0;
    for (int h = 0; h < 8 && all; h++) {
      CarBox b; memset(&b, 0, sizeof b); float a = h * 0.7853982f; b.x = x; b.z = z; b.fx = sinf(a); b.fz = cosf(a); b.hw = 1.10f; b.hl = 2.675f; b.y = yy; b.lo = 0.35f; b.hi = 1.6f;
      colProbeCar(&W, &b); if (b.maxDepth <= .3f) all = 0; else if (b.maxDepth > worst) worst = b.maxDepth;
    }
    if (all && !nearProp(x, y, z, 3.f) && !inDeathXZ(x, y, z)) add("embedded", x, y, z, 5.f, "кузов внутри геометрии на любом из 8 курсов (осадка до %.1f м): опора есть, места нет", worst);
  }
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "worldscan LEVEL.shr LEVEL_NO OUT.tsv [--detectors inv,pass,hole,edge,embed]\n"); return 2; }
  LV = atoi(argv[2]); if (sceneLoad(argv[1])) { fprintf(stderr, "worldscan: не прочитан %s\n", argv[1]); return 2; }
  const char *det = "inv,pass,hole,edge,offset,bush,embed"; for (int i = 4; i + 1 < argc; i++) { if (!strcmp(argv[i], "--detectors")) det = argv[++i]; else if (!strcmp(argv[i], "--foltex")) loadFol(argv[++i]); }
  loadRender(); loadProps();
  fprintf(stderr, "уровень %d: рисуемых треугольников %u, предметов %u, коллизия: коробок %u цилиндров %u заборов %u треугольников %u\n", LV, NT, nProp, W.nbox, W.ncyl, W.nseg, W.ntri);
  if (strstr(det, "inv")) detInvisible();
  if (strstr(det, "pass")) detPass();
  if (strstr(det, "hole")) detHole();
  if (strstr(det, "edge")) detEdge();
  if (strstr(det, "offset")) detOffset();
  if (strstr(det, "bush")) detBush();
  if (strstr(det, "embed")) detEmbedded();
  // склейка: тип + клетка 4 м -> одна строка, вес = максимум + log повторов
  qsort(F, nF, sizeof *F, cmpF);
  FILE *o = fopen(argv[3], "w"); if (!o) return 2;
  unsigned out = 0; int counts[8] = {0}; const char *tn[8] = {"invisible_wall", "pass_through", "hole", "void_edge", "embedded", "ground_offset", "bush_holds"};
  for (unsigned i = 0; i < nF; ) {
    unsigned j = i; float sx = 0, sy = 0, sz = 0, wmax = 0; Fnd *best = &F[i];
    while (j < nF && !cmpF(&F[i], &F[j])) { sx += F[j].x; sy += F[j].y; sz += F[j].z; if (F[j].w > wmax) { wmax = F[j].w; best = &F[j]; } j++; }
    int n = (int)(j - i); float w = fminf(10.f, wmax + log2f((float)n));
    fprintf(o, "%d\t%.1f\t%.1f\t%.1f\t%s\t%.1f\t0\t0\t%s%s\n", LV, sx / n, sy / n, sz / n, best->type, w, best->desc, n > 1 ? " (+склеено)" : "");
    for (int t = 0; t < 7; t++) if (!strcmp(best->type, tn[t])) counts[t] += 1;
    out++; i = j;
  }
  fclose(o);
  fprintf(stderr, "находок %u (до склейки %u): invisible_wall %d, pass_through %d, hole %d, void_edge %d, embedded %d, ground_offset %d, bush_holds %d\n", out, nF, counts[0], counts[1], counts[2], counts[3], counts[4], counts[5], counts[6]);
  return 0;
}
