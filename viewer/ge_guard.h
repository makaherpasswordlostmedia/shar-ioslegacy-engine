// ge_guard.h — правка Роба 340 («по краям экрана иногда обламывается тень от деревьев на траве»; родня правки 325, fe_billcut.h).
// GE PSP режет треугольник по near (GU_CLIP_PLANES), а вершину, ушедшую после среза дальше ±2048 px от центра экрана
// (защитная полоса), не терпит: треугольник выбрасывается ЦЕЛИКОМ (кадры железа TEST 10, правка 325; программная отрисовка
// безголового эмулятора делает так же, оконный — нет). Город нарезан экспортом до рёбер 7 м по земле и 14 м по стенам — при
// ближней плоскости 1,5 м этого хватает (полоса у near ±13,7 м). Но пешком у стены, дерева, машины ближняя плоскость
// опускается до 0,25–0,3 м (homer.c camNear, main.c frameNear) — полоса у near сужается до ±2,3 м, и треугольник земли или
// тени-наклейки (tex «тень дерева», 7 м), который краем уходит за камеру, у края кадра пропадает: светлый клин травы без тени
// или тёмная дыра (модель GE tests/guard340/ge340.py на позах CAMF эмулятора).
// Правило: треугольник, который GE нарисовал бы не целиком (вершина ближе near·GG_NEAR или дальше GG_SAFE px от центра), не
// касающийся экрана — отдаём GE как есть (не виден); касающийся — режем на процессоре по пирамиде защитной полосы (near·GG_NEAR и
// ±GG_PX от центра экрана): выпуклый многоугольник до 8 вершин, веером. Всё, что на экране, остаётся; GE больше не режет и не
// выбрасывает. Без зависимостей от PSP: tests/guard340/guard_host.c собирает этот файл на Маке.
#ifndef GE_GUARD_H
#define GE_GUARD_H

#define GG_PX 1800.f        // край пирамиды среза, px от центра (полоса GE — 2048; экран — 240 × 136)
#define GG_SAFE 1900.f      // вершина дальше — треугольник под риском (запас к 2048 на float24 GE)
#define GG_NEAR 1.002f      // срез чуть дальше near: GE сам больше не режет (полоска 0,2 % near — меньше пикселя)
#define GG_MAXV 8           // 3 вершины + не больше одной на каждую из 5 плоскостей
#define GG_ZFAR 20.f        // м: треугольник целиком дальше — не под риском (вершине за полосой нужно |x| > 7·z: при рёбрах
                            // города до 14 м, у редких полос до 38 м, видимая часть так далеко вбок не уходит)

typedef struct { float c[3], l[3], t[2], k[4]; } GgV;   // оси камеры (x вправо, y вверх, z вперёд); позиция куска; uv; цвет
typedef struct { float tvx, tvy, zn; } GgCam;            // tg половины угла по x и y, ближняя плоскость кадра

static inline float ggDist(int pl, const GgV *v, float gx, float gy, float zc) {   // >= 0 — внутри
  float x = v->c[0], y = v->c[1], z = v->c[2];
  switch (pl) {
    case 0: return z - zc;
    case 1: return gx * z - x;
    case 2: return gx * z + x;
    case 3: return gy * z - y;
    default: return gy * z + y;
  }
}

// 0 — треугольник GE нарисует целиком (или он целиком за одной боковой гранью кадра — не виден): отдать GE как есть;
// 1 — под риском и касается кадра: резать (ggCut)
static inline int ggRisk(const GgV *a, const GgV *b, const GgV *c, const GgCam *k) {
  if (a->c[2] >= GG_ZFAR && b->c[2] >= GG_ZFAR && c->c[2] >= GG_ZFAR) return 0;   // весь дальше GG_ZFAR (движок проверяет это первым)
  const GgV *v[3] = {a, b, c}; int out[5] = {0, 0, 0, 0, 0}, risk = 0;
  float sx = k->tvx * (GG_SAFE / 240.f), sy = k->tvy * (GG_SAFE / 136.f);
  for (int i = 0; i < 3; i++) {
    float x = v[i]->c[0], y = v[i]->c[1], z = v[i]->c[2];
    out[0] += z < k->zn; out[1] += x > k->tvx * z; out[2] += -x > k->tvx * z; out[3] += y > k->tvy * z; out[4] += -y > k->tvy * z;
    if (z < k->zn * GG_NEAR || x > sx * z || -x > sx * z || y > sy * z || -y > sy * z) risk = 1;
  }
  for (int i = 0; i < 5; i++) if (out[i] == 3) return 0;   // целиком за near или за одной гранью кадра — на экране ничего
  return risk;
}

// бокс куска/клетки (8 углов в осях камеры): 0 — целиком в пирамиде полосы (все треугольники внутри него GE нарисует целиком)
// или целиком за near / за одной гранью кадра (не виден); 1 — внутри могут быть треугольники под риском
static inline int ggBoxRisk(const float c[8][3], const GgCam *k) {
  int out[5] = {0, 0, 0, 0, 0}, risk = 0; float sx = k->tvx * (GG_SAFE / 240.f), sy = k->tvy * (GG_SAFE / 136.f);
  for (int i = 0; i < 8; i++) {
    float x = c[i][0], y = c[i][1], z = c[i][2];
    out[0] += z < k->zn; out[1] += x > k->tvx * z; out[2] += -x > k->tvx * z; out[3] += y > k->tvy * z; out[4] += -y > k->tvy * z;
    if (z < k->zn * GG_NEAR || x > sx * z || -x > sx * z || y > sy * z || -y > sy * z) risk = 1;
  }
  for (int i = 0; i < 5; i++) if (out[i] == 8) return 0;
  return risk;
}

// бокс мира (мин xyz, макс xyz) -> 8 углов в осях камеры (глаз E, оси R вправо, U вверх, F вперёд) -> ggBoxRisk.
// main.c ggBoxRiskW (клетка и кусок у камеры, правки 340 и render_fast О11); tests/render/host.c — та же функция на хосте
static inline int ggBoxRiskAx(const float bb[6], const float E[3], const float R[3], const float U[3], const float F[3], const GgCam *k) {
  float c[8][3];
  for (int i = 0; i < 8; i++) {
    float w[3] = {bb[(i & 1) ? 3 : 0] - E[0], bb[(i & 2) ? 4 : 1] - E[1], bb[(i & 4) ? 5 : 2] - E[2]};
    c[i][0] = w[0] * R[0] + w[1] * R[1] + w[2] * R[2]; c[i][1] = w[0] * U[0] + w[1] * U[1] + w[2] * U[2]; c[i][2] = w[0] * F[0] + w[1] * F[1] + w[2] * F[2];
  }
  return ggBoxRisk((const float (*)[3])c, k);
}

// срез треугольника по пирамиде полосы -> многоугольник (вершин 0 или 3..8) в out, обход как у треугольника
static inline int ggCutRef(const GgV *a, const GgV *b, const GgV *c, const GgCam *k, GgV *out) {
  float gx = k->tvx * (GG_PX / 240.f), gy = k->tvy * (GG_PX / 136.f), zc = k->zn * GG_NEAR;
  GgV p[GG_MAXV], q[GG_MAXV]; int n = 3;
  p[0] = *a; p[1] = *b; p[2] = *c;
  for (int pl = 0; pl < 5 && n >= 3; pl++) {
    int m = 0;
    for (int i = 0; i < n && m < GG_MAXV; i++) {
      const GgV *u = &p[i], *w = &p[i + 1 < n ? i + 1 : 0];
      float du = ggDist(pl, u, gx, gy, zc), dw = ggDist(pl, w, gx, gy, zc);
      if (du >= 0.f) q[m++] = *u;
      if ((du >= 0.f) != (dw >= 0.f) && m < GG_MAXV) {
        float s = du / (du - dw); GgV *o = &q[m++];     // знаки разные — знаменатель не ноль
        for (int j = 0; j < 3; j++) { o->c[j] = u->c[j] + (w->c[j] - u->c[j]) * s; o->l[j] = u->l[j] + (w->l[j] - u->l[j]) * s; }
        for (int j = 0; j < 2; j++) o->t[j] = u->t[j] + (w->t[j] - u->t[j]) * s;
        for (int j = 0; j < 4; j++) o->k[j] = u->k[j] + (w->k[j] - u->k[j]) * s;
      }
    }
    for (int i = 0; i < m; i++) p[i] = q[i];
    n = m;
  }
  if (n < 3) return 0;
  for (int i = 0; i < n; i++) out[i] = p[i];
  return n;
}
// Быстрый путь (план А3/А4, 10.10): тот же срез, но плоскость, с которой все вершины многоугольника внутри, не проходится вовсе (раньше каждая из 5 плоскостей копировала
// все GgV по 48 Б дважды и считала расстояния по два раза на ребро). Расстояния считаются один раз на вершину и используются в формуле пересечения те же самые, так что
// результат побитово совпадает с ggCutRef (tests/ggcut/host.c). GGCUT_FAST_OLD=1 — прежний ggCutRef
#ifndef GGCUT_FAST_OLD
#define GGCUT_FAST_OLD 0
#endif
static inline int ggCutFast(const GgV *a, const GgV *b, const GgV *c, const GgCam *k, GgV *out) {
  float gx = k->tvx * (GG_PX / 240.f), gy = k->tvy * (GG_PX / 136.f), zc = k->zn * GG_NEAR;
  GgV p[GG_MAXV], q[GG_MAXV]; int n = 3;
  p[0] = *a; p[1] = *b; p[2] = *c;
  GgV *cur = p, *oth = q;
  for (int pl = 0; pl < 5 && n >= 3; pl++) {
    float d[GG_MAXV]; int any = 0;
    for (int i = 0; i < n; i++) { d[i] = ggDist(pl, &cur[i], gx, gy, zc); if (d[i] < 0.f) any = 1; }
    if (!any) continue;                       // все внутри: прежний цикл вернул бы те же вершины в том же порядке
    int m = 0;
    for (int i = 0; i < n && m < GG_MAXV; i++) {
      const GgV *u = &cur[i], *w = &cur[i + 1 < n ? i + 1 : 0]; float du = d[i], dw = d[i + 1 < n ? i + 1 : 0];
      if (du >= 0.f) oth[m++] = *u;
      if ((du >= 0.f) != (dw >= 0.f) && m < GG_MAXV) {
        float s = du / (du - dw); GgV *o = &oth[m++];
        for (int j = 0; j < 3; j++) { o->c[j] = u->c[j] + (w->c[j] - u->c[j]) * s; o->l[j] = u->l[j] + (w->l[j] - u->l[j]) * s; }
        for (int j = 0; j < 2; j++) o->t[j] = u->t[j] + (w->t[j] - u->t[j]) * s;
        for (int j = 0; j < 4; j++) o->k[j] = u->k[j] + (w->k[j] - u->k[j]) * s;
      }
    }
    GgV *t = cur; cur = oth; oth = t; n = m;
  }
  if (n < 3) return 0;
  for (int i = 0; i < n; i++) out[i] = cur[i];
  return n;
}
static inline int ggCut(const GgV *a, const GgV *b, const GgV *c, const GgCam *k, GgV *out) { return GGCUT_FAST_OLD ? ggCutRef(a, b, c, k, out) : ggCutFast(a, b, c, k, out); }
#endif
