// fe_billcut.h — правка Роба 325 (повторы 244, 265, 293: «при наезде к газете часть пола будто пропадает», только на PSP).
// Подсветки гостиной меню (FeBill: свет из окна на полу window.bmp, конус лампы, отсвет телевизора, свет на потолке) — квад из
// двух треугольников, который движок строит на лету; нарезки у камеры у них не было (её делает экспорт, и только для кусков).
// При наезде к газете вершина квада после среза GE по near уходит дальше ±2048 px от центра (защитная полоса GE) — железо
// выбрасывает треугольник ЦЕЛИКОМ, эмулятор рисует: свет из окна на полу (квад 4,4 × 4,5 м) у PSP пропадает половиной
// (tl ~30), потом целиком (tl ~35,6) — пол у газеты резко темнеет. Улики: кадры fecap TEST 10 (build/psp-tour/20261004-2133,
// fe293_32 светлый, fe293_33 тёмный) совпадают с моделью GE (tests/fe_guard/ge325.py), у оригинала (близнец PCSX2) пол у газеты
// светлый до ириса. Правило: квад, который GE нарисовал бы не целиком (вершина ближе near·1,02 или дальше FE_CUT_PX от центра),
// режем на процессоре по пирамиде защитной полосы (near·1,02 и ±1800 px от центра экрана) — выпуклый многоугольник не больше
// 9 вершин, рисуется веером. Всё, что на экране, остаётся (пирамида шире экрана в 7 раз), ни одна вершина не выходит за полосу,
// GE сам больше ничего не режет. Квад целиком внутри — -1, движок рисует полосой, как раньше (байт в байт).
// Без зависимостей от PSP: tests/fe_guard/billcut_host.c собирает этот файл на Маке (гейт tests/fe_guard/gate325.sh).
#ifndef FE_BILLCUT_H
#define FE_BILLCUT_H

typedef struct { float p[3], r[3], u[3], f[3], tvx, tvy, zn; } FeCutCam;   // глаз; оси вправо, вверх, вперёд; tg половины угла; near
typedef struct { float w[3], s, t; } FeCutVert;                            // вершина: мир + uv (0..1)
#define FE_CUT_PX 1800.f       // край пирамиды среза, px от центра экрана (защитная полоса GE — 2048, экран — 240 × 136)
#define FE_CUT_NEAR 1.02f      // срез чуть дальше near: GE сам больше не режет
#define FE_CUT_MAXV 12         // 4 вершины + не больше одной на каждую из 5 плоскостей = 9

typedef struct { float c[3], w[3], t[2]; } FeCutV;
static inline float feCutDist(int pl, const FeCutV *v, float gx, float gy, float zc) {   // >= 0 — внутри
  float x = v->c[0], y = v->c[1], z = v->c[2];
  switch (pl) {
    case 0: return z - zc;
    case 1: return gx * z - x;
    case 2: return gx * z + x;
    case 3: return gy * z - y;
    default: return gy * z + y;
  }
}

// P, T — 4 вершины квада в порядке полосы GU_TRIANGLE_STRIP (0 1 2 3: треугольники 012 и 123), мир и uv.
// -1 — квад целиком внутри пирамиды (рисовать полосой, как раньше); иначе число вершин веера в out (0 — не виден; 3..9)
static inline int feBillCut(const float P[4][3], const float T[4][2], const FeCutCam *k, FeCutVert *out) {
  float gx = k->tvx * (FE_CUT_PX / 240.f), gy = k->tvy * (FE_CUT_PX / 136.f), zc = k->zn * FE_CUT_NEAR;
  static const int ord[4] = {0, 1, 3, 2};                  // полоса -> обход по контуру
  FeCutV a[FE_CUT_MAXV], b[FE_CUT_MAXV]; int n = 4, inside = 1;
  for (int i = 0; i < 4; i++) {
    const float *p = P[ord[i]]; FeCutV *v = &a[i];
    float d[3] = {p[0] - k->p[0], p[1] - k->p[1], p[2] - k->p[2]};
    v->c[0] = d[0] * k->r[0] + d[1] * k->r[1] + d[2] * k->r[2];
    v->c[1] = d[0] * k->u[0] + d[1] * k->u[1] + d[2] * k->u[2];
    v->c[2] = d[0] * k->f[0] + d[1] * k->f[1] + d[2] * k->f[2];
    v->w[0] = p[0]; v->w[1] = p[1]; v->w[2] = p[2]; v->t[0] = T[ord[i]][0]; v->t[1] = T[ord[i]][1];
    for (int pl = 0; pl < 5; pl++) if (feCutDist(pl, v, gx, gy, zc) < 0.f) inside = 0;
  }
  if (inside) return -1;
  for (int pl = 0; pl < 5 && n >= 3; pl++) {               // Сазерленд — Ходжман: плоскость за плоскостью
    int m = 0;
    for (int i = 0; i < n && m < FE_CUT_MAXV; i++) {
      const FeCutV *p = &a[i], *q = &a[i + 1 < n ? i + 1 : 0];
      float dp = feCutDist(pl, p, gx, gy, zc), dq = feCutDist(pl, q, gx, gy, zc);
      if (dp >= 0.f) b[m++] = *p;
      if ((dp >= 0.f) != (dq >= 0.f) && m < FE_CUT_MAXV) {
        float s = dp / (dp - dq); FeCutV *o = &b[m++];     // знаки разные — знаменатель не ноль
        for (int j = 0; j < 3; j++) { o->c[j] = p->c[j] + (q->c[j] - p->c[j]) * s; o->w[j] = p->w[j] + (q->w[j] - p->w[j]) * s; }
        o->t[0] = p->t[0] + (q->t[0] - p->t[0]) * s; o->t[1] = p->t[1] + (q->t[1] - p->t[1]) * s;
      }
    }
    for (int i = 0; i < m; i++) a[i] = b[i];
    n = m;
  }
  if (n < 3) return 0;
  for (int i = 0; i < n; i++) {
    out[i].w[0] = a[i].w[0]; out[i].w[1] = a[i].w[1]; out[i].w[2] = a[i].w[2]; out[i].s = a[i].t[0]; out[i].t = a[i].t[1];
  }
  return n;
}
#endif
