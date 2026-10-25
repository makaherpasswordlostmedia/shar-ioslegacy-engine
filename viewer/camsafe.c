// Правка Роба 331: камера никогда не внутри геометрии — замер и свободная ближняя плоскость (см. camsafe.h)
#include <math.h>
#include <string.h>
#include "camsafe.h"

// отрезок a -> b против кузова (раздутого на pad): 1 — пересекает; *tin — вход (0, если начало внутри), *in — начало внутри
static int segBox(const CsBox *B, const float a[3], const float b[3], float pad, float *tin, int *in) {
  float rx = -B->fz, rz = B->fx;
  float pa[3], pb[3];
  pa[0] = (a[0] - B->x) * B->fx + (a[2] - B->z) * B->fz; pa[2] = (a[0] - B->x) * rx + (a[2] - B->z) * rz;
  pb[0] = (b[0] - B->x) * B->fx + (b[2] - B->z) * B->fz; pb[2] = (b[0] - B->x) * rx + (b[2] - B->z) * rz;
  pa[1] = a[1] - (B->y + B->gx * (a[0] - B->x) + B->gz * (a[2] - B->z));   // высота над полом кузова (пол — плоскость: линейно)
  pb[1] = b[1] - (B->y + B->gx * (b[0] - B->x) + B->gz * (b[2] - B->z));
  float lo[3] = {-B->hl - pad, B->lo - pad, -B->hw - pad}, hi[3] = {B->hl + pad, B->hi + pad, B->hw + pad}, t0 = 0.f, t1 = 1.f;
  *in = pa[0] > lo[0] && pa[0] < hi[0] && pa[1] > lo[1] && pa[1] < hi[1] && pa[2] > lo[2] && pa[2] < hi[2];
  for (int i = 0; i < 3; i++) {
    float d = pb[i] - pa[i];
    if (fabsf(d) < 1e-7f) { if (pa[i] < lo[i] || pa[i] > hi[i]) return 0; continue; }
    float u = (lo[i] - pa[i]) / d, v = (hi[i] - pa[i]) / d; if (u > v) { float w = u; u = v; v = w; }
    if (u > t0) t0 = u; if (v < t1) t1 = v; if (t0 > t1) return 0;
  }
  *tin = t0; return 1;
}
// отрезок против вертикального цилиндра (раздутого на pad)
static int segCyl(const CsCyl *C, const float a[3], const float b[3], float pad, float *tin, int *in) {
  float r = C->r + pad, y0 = C->y0 - pad, y1 = C->y1 + pad;
  float ax = a[0] - C->x, az = a[2] - C->z, dx = b[0] - a[0], dz = b[2] - a[2], dy = b[1] - a[1];
  *in = ax * ax + az * az < r * r && a[1] > y0 && a[1] < y1;
  float t0 = 0.f, t1 = 1.f, A = dx * dx + dz * dz, Bq = ax * dx + az * dz, Cq = ax * ax + az * az - r * r;
  if (A < 1e-9f) { if (Cq > 0.f) return 0; }
  else {
    float D = Bq * Bq - A * Cq; if (D < 0.f) return 0;
    float s = sqrtf(D), u = (-Bq - s) / A, v = (-Bq + s) / A;
    if (u > t0) t0 = u; if (v < t1) t1 = v; if (t0 > t1) return 0;
  }
  if (fabsf(dy) < 1e-7f) { if (a[1] < y0 || a[1] > y1) return 0; }
  else {
    float u = (y0 - a[1]) / dy, v = (y1 - a[1]) / dy; if (u > v) { float w = u; u = v; v = w; }
    if (u > t0) t0 = u; if (v < t1) t1 = v; if (t0 > t1) return 0;
  }
  *tin = t0; return 1;
}

float csTriFrac(const CsScene *s, const float a[3], const float b[3]) {
  float d[3] = {b[0] - a[0], b[1] - a[1], b[2] - a[2]}, best = 1.f;
  for (int i = 0; i < s->ntri; i++) {
    const float *t = s->tri[i];
    float e1[3] = {t[3] - t[0], t[4] - t[1], t[5] - t[2]}, e2[3] = {t[6] - t[0], t[7] - t[1], t[8] - t[2]};
    float p[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]};
    float det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2];
    if (det > -1e-7f && det < 1e-7f) continue;
    float id = 1.f / det, q0 = a[0] - t[0], q1 = a[1] - t[1], q2 = a[2] - t[2];
    float u = (q0 * p[0] + q1 * p[1] + q2 * p[2]) * id; if (u < 0.f || u > 1.f) continue;
    float qv[3] = {q1 * e1[2] - q2 * e1[1], q2 * e1[0] - q0 * e1[2], q0 * e1[1] - q1 * e1[0]};
    float v = (d[0] * qv[0] + d[1] * qv[1] + d[2] * qv[2]) * id; if (v < 0.f || u + v > 1.f) continue;
    float tt = (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2]) * id;
    if (tt > 0.f && tt < best) best = tt;
  }
  return best;
}
// №791: то же, что csTriFrac, и наклон нормали задетого треугольника (|ny| длины 1): пол или стена
static float csTriFracN(const CsScene *s, const float a[3], const float b[3], float *nyOut) {
  float d[3] = {b[0] - a[0], b[1] - a[1], b[2] - a[2]}, best = 1.f; *nyOut = 0.f;
  for (int i = 0; i < s->ntri; i++) {
    const float *t = s->tri[i];
    float e1[3] = {t[3] - t[0], t[4] - t[1], t[5] - t[2]}, e2[3] = {t[6] - t[0], t[7] - t[1], t[8] - t[2]};
    float p[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]};
    float det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2];
    if (det > -1e-7f && det < 1e-7f) continue;
    float id = 1.f / det, q0 = a[0] - t[0], q1 = a[1] - t[1], q2 = a[2] - t[2];
    float u = (q0 * p[0] + q1 * p[1] + q2 * p[2]) * id; if (u < 0.f || u > 1.f) continue;
    float qv[3] = {q1 * e1[2] - q2 * e1[1], q2 * e1[0] - q0 * e1[2], q0 * e1[1] - q1 * e1[0]};
    float v = (d[0] * qv[0] + d[1] * qv[1] + d[2] * qv[2]) * id; if (v < 0.f || u + v > 1.f) continue;
    float tt = (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2]) * id;
    if (tt > 0.f && tt < best) { best = tt;
      float nx = e1[1] * e2[2] - e1[2] * e2[1], ny = e1[2] * e2[0] - e1[0] * e2[2], nz = e1[0] * e2[1] - e1[1] * e2[0], nl = sqrtf(nx * nx + ny * ny + nz * nz);
      *nyOut = nl > 1e-9f ? fabsf(ny) / nl : 0.f; }
  }
  return best;
}
unsigned csRayCalls, csNfCalls, csRaysMismatch;
// CAMPERF (ускорение камеры, 23.10): лучи ближней плоскости — одним пакетом к коллизии (colRaysFrac), остальное (сетка, тела) по одному; ответ тот же. CAM_RAYS_OLD=1 / flag camraysold 1 — как было
#ifndef CAM_RAYS_OLD
#define CAM_RAYS_OLD 0
#endif
int camRaysOld = CAM_RAYS_OLD, camRaysVerify;
static float csRayFracC(const CsScene *s, const float a[3], const float b[3], int bodies, float colf) {   // colf >= 0 — ответ коллизии уже посчитан пакетом
  float f = 1.f, t; int in; csRayCalls++;
  if ((bodies & 1) && s->w) {
    if ((bodies & 128) && colf < 0.f) {   // №922: высокие стены продолжены вверх (глаз не над фасадом, за которым крыша без коллизии), если над верхом стены в CAM_WALL_UP есть видимая геометрия
      colSegUp = CAM_WALL_UP; float f1 = colRayFrac(s->w, a, b, 0); colSegUp = 0.f;   // свободный луч с продлением свободен и без него — один обход клеток
      f = f1;
      if (f1 < 1.f) { f = colRayFrac(s->w, a, b, 0);
        if (f1 < f) { float h[3] = {a[0] + (b[0] - a[0]) * f1, a[1] + (b[1] - a[1]) * f1, a[2] + (b[2] - a[2]) * f1}; if (!s->roofAbove || s->roofAbove(h)) f = f1; } } }
    else f = colf >= 0.f ? colf : colRayFrac(s->w, a, b, 0);
  }
  if (bodies & 8) {   // видимая геометрия города: треугольники (медленно) или сетка занятости (CAM_GEOM_FAST)
    if (s->ntri && s->useTri) { float g = csTriFrac(s, a, b); if (g < f) f = g; }
    if (s->geomRay) { float g = s->geomRay(a, b, (bodies & 16) ? 0.f : CS_GEOM_SKIP); if (g < f) f = g; } }
  if (bodies & 38) {
    for (int i = 0; i < s->nbox; i++) { int o = s->box[i].own;
      if (o == 2 ? !(bodies & 32) : !((bodies & 6) && ((bodies & 2) || !o))) continue;   // own 2 — стейтпроп (№727), только маска 32
      if (segBox(&s->box[i], a, b, 0.f, &t, &in) && !in && t < f) f = t; }
    if ((bodies & 6) && !(bodies & 64)) for (int i = 0; i < s->ncyl; i++)   // 64 — №916в: луч промежуточного глаза не считает людей (идущий рядом с Гомером не обрывает перелёт рывком)
       if (segCyl(&s->cyl[i], a, b, 0.f, &t, &in) && !in && t < f) f = t;
  }
  return f;
}
float csRayFrac(const CsScene *s, const float a[3], const float b[3], int bodies) { return csRayFracC(s, a, b, bodies, -1.f); }
int csInBody(const CsScene *s, const float p[3], float pad) {
  float t; int in;
  for (int i = 0; i < s->nbox; i++) { if (s->box[i].own == 2) continue; segBox(&s->box[i], p, p, pad, &t, &in); if (in) return 1; }
  for (int i = 0; i < s->ncyl; i++) { segCyl(&s->cyl[i], p, p, pad, &t, &in); if (in) return 1; }
  return 0;
}
void csBasis(const float f[3], float r[3], float u[3]) {
  // вправо = f × (0,1,0), вверх = r × f (sceGumLookAt); взгляд строго вверх/вниз — ось x
  r[0] = -f[2]; r[1] = 0.f; r[2] = f[0];
  float l = sqrtf(r[0] * r[0] + r[2] * r[2]); if (l < 1e-5f) { r[0] = 1.f; r[2] = 0.f; } else { r[0] /= l; r[2] /= l; }
  u[0] = r[1] * f[2] - r[2] * f[1]; u[1] = r[2] * f[0] - r[0] * f[2]; u[2] = r[0] * f[1] - r[1] * f[0];
}
static void nearPt(const float e[3], const float f[3], const float r[3], const float u[3], float n, float sx, float sy, float o[3]) {
  for (int k = 0; k < 3; k++) o[k] = e[k] + n * (f[k] + sx * r[k] + sy * u[k]);
}

// CAM_NEARGEOM: ближняя плоскость учитывает и видимую геометрию города (сетка), не только коллизию и тела — глаз в изгороди/у стены вплотную негоден (TEST19 будка)
#ifndef CAM_NEARGEOM_OLD
#define CAM_NEARGEOM_OLD 0
#endif
int camNearGeomOld = CAM_NEARGEOM_OLD;
float csDbgVf[4];   // №791 замер: точка видимого пола, задетая ближней плоскостью (x, y, z) и коллизия под ней (y)
#ifndef CAM_NEAR_DENSE_OLD
#define CAM_NEAR_DENSE_OLD 0
#endif
int camNearDenseOld = CAM_NEAR_DENSE_OLD;
#define CS_NEARMASK (camNearGeomOld ? (3 | 32) : (3 | 8 | 16 | 32))   // 32 — стейтпропы у глаза (№727)
float csNearFree(const CsScene *s, const float eye[3], const float f[3], float tanV, float tanH, float nmax) {
  csNfCalls++;
  float r[3], u[3], D = nmax / CS_NEAR_K, free = D, p[3];   // лучи — на глубину nmax / CS_NEAR_K: свободно — ближняя плоскость прежняя
  csBasis(f, r, u);
  // №727 (Роб 17.10: «ничего не должно обрезаться по краям кадра»): 3 × 3 луча пропускали предмет, входящий в кадр сбоку между ними (ящик внизу справа,
  // угол дома у края) — срез 1,5 м резал его раньше, чем он уходил из кадра. Теперь по 5 точек на каждой стороне (16 лучей по краю кадра) и центр.
  // CAM_NEAR_DENSE_OLD=1 / flag camneardenseold 1 — прежние 3 × 3
  if (camNearDenseOld) {
    for (int sy = -1; sy <= 1; sy++) for (int sx = -1; sx <= 1; sx++) {   // 3 × 3 луча: углы, середины сторон, центр
      nearPt(eye, f, r, u, D, sx * tanH, sy * tanV, p);
      float fr = csRayFrac(s, eye, p, CS_NEARMASK) * D; if (fr < free) free = fr;
    }
  } else if (!camRaysOld && s->w) {   // CAMPERF: 17 лучей к коллизии одним обходом клеток
    float A[17][3], B[17][3], cf[17]; int m = 0;
    for (int sy = -2; sy <= 2; sy++) for (int sx = -2; sx <= 2; sx++) {
      if (sx > -2 && sx < 2 && sy > -2 && sy < 2 && (sx || sy)) continue;   // край кадра (16) и центр
      nearPt(eye, f, r, u, D, sx * .5f * tanH, sy * .5f * tanV, B[m]); memcpy(A[m], eye, 12); m++;
    }
    colRaysFrac(s->w, m, (const float (*)[3])A, (const float (*)[3])B, cf);
    for (int i = 0; i < m; i++) {
      float fr = csRayFracC(s, eye, B[i], CS_NEARMASK, cf[i]) * D; if (fr < free) free = fr;
      if (camRaysVerify) { float g = csRayFrac(s, eye, B[i], CS_NEARMASK) * D; if (fabsf(g - fr) > 1e-6f) csRaysMismatch++; }
    }
  } else for (int sy = -2; sy <= 2; sy++) for (int sx = -2; sx <= 2; sx++) {
    if (sx > -2 && sx < 2 && sy > -2 && sy < 2 && (sx || sy)) continue;   // край кадра (16) и центр
    nearPt(eye, f, r, u, D, sx * .5f * tanH, sy * .5f * tanV, p);
    float fr = csRayFrac(s, eye, p, CS_NEARMASK) * D; if (fr < free) free = fr;
  }
  float n = fminf(nmax, free * CS_NEAR_K);
  for (;;) {   // стороны прямоугольника на этой глубине (угол дома, столб, край забора между лучами); не сошлось — ближе
    float c[4][3]; int bad = 0;
    nearPt(eye, f, r, u, n, -tanH, -tanV, c[0]); nearPt(eye, f, r, u, n, tanH, -tanV, c[1]);
    nearPt(eye, f, r, u, n, tanH, tanV, c[2]); nearPt(eye, f, r, u, n, -tanH, tanV, c[3]);
    if (!camRaysOld && s->w && !camNearDenseOld) {   // CAMPERF: 4 стороны — тоже пакетом
      float A[4][3], B[4][3], cf[4]; for (int i = 0; i < 4; i++) { memcpy(A[i], c[i], 12); memcpy(B[i], c[(i + 1) & 3], 12); }
      colRaysFrac(s->w, 4, (const float (*)[3])A, (const float (*)[3])B, cf);
      for (int i = 0; i < 4 && !bad; i++) { bad = csRayFracC(s, A[i], B[i], CS_NEARMASK, cf[i]) < 1.f;
        if (camRaysVerify) { int g = csRayFrac(s, A[i], B[i], CS_NEARMASK) < 1.f; if (g != bad) csRaysMismatch++; } }
    } else
    for (int i = 0; i < 4 && !bad; i++) bad = csRayFrac(s, c[i], c[(i + 1) & 3], CS_NEARMASK) < 1.f;
    if (!bad) return n;
    n *= .7f;
    if (n < CS_NEAR_MIN) return 0.f;   // меньше CS_NEAR_MIN — места перед глазом нет (точнее не нужно)
  }
}

int csProbe(const CsScene *s, const float eye[3], const float f[3], float tanV, float tanH, float near, const float pivot[3]) {
  float r[3], u[3], c[4][3], m[4][3], t; int in, fl = 0;
  csBasis(f, r, u);
  nearPt(eye, f, r, u, near, -tanH, -tanV, c[0]); nearPt(eye, f, r, u, near, tanH, -tanV, c[1]);
  nearPt(eye, f, r, u, near, tanH, tanV, c[2]); nearPt(eye, f, r, u, near, -tanH, tanV, c[3]);
  nearPt(eye, f, r, u, near, 0.f, -tanV, m[0]); nearPt(eye, f, r, u, near, tanH, 0.f, m[1]);
  nearPt(eye, f, r, u, near, 0.f, tanV, m[2]); nearPt(eye, f, r, u, near, -tanH, 0.f, m[3]);
  // отрезки ближней плоскости: глаз -> 4 угла, глаз -> 4 середины сторон, 4 стороны
  const float *A[12], *B[12];
  for (int i = 0; i < 4; i++) { A[i] = eye; B[i] = c[i]; A[4 + i] = eye; B[4 + i] = m[i]; A[8 + i] = c[i]; B[8 + i] = c[(i + 1) & 3]; }
  if (s->w) {
    if (colRayFrac(s->w, pivot, eye, 0) < .999f) fl |= CS_IN_EYE;
    for (int i = 0; i < 12 && !(fl & CS_IN_NEAR); i++) if (colRayFrac(s->w, A[i], B[i], 0) < .999f) fl |= CS_IN_NEAR;
    for (int i = -1; i < 4 && !(fl & CS_IN_GROUND); i++) {   // глаз и углы: опора коллизии между точкой и высотой опоры камеры
      const float *p = i < 0 ? eye : c[i]; float gy;
      if (pivot[1] > p[1] + .01f && colGround(s->w, p[0], p[2], pivot[1], p[1], &gy, 0) && gy > p[1] + .01f) fl |= CS_IN_GROUND;
    }
  }
  if (s->ntri && csTriFrac(s, pivot, eye) < .999f) fl |= CS_IN_GEOM;
  if (s->ntri) for (int i = 0; i < 12 && (fl & (CS_IN_VFLOOR | CS_IN_VWALL)) != (CS_IN_VFLOOR | CS_IN_VWALL); i++) {   // №791: отрезки ближней плоскости против видимых треугольников
    float ny, tt = csTriFracN(s, A[i], B[i], &ny);
    if (tt < .999f) { fl |= ny > .8f ? CS_IN_VFLOOR : CS_IN_VWALL;
      if (ny > .8f) { float P[3]; for (int k = 0; k < 3; k++) P[k] = A[i][k] + (B[i][k] - A[i][k]) * tt;   // замер: видимый пол против коллизии в точке
        csDbgVf[0] = P[0]; csDbgVf[1] = P[1]; csDbgVf[2] = P[2]; csDbgVf[3] = -999.f; float g;
        if (s->w && colGround(s->w, P[0], P[2], P[1] + 2.f, P[1] - 4.f, &g, 0)) csDbgVf[3] = g; } } }
  for (int i = 0; i < s->nbox; i++) {
    const CsBox *b = &s->box[i]; int hit = 0;
    segBox(b, eye, eye, 0.f, &t, &in); hit = in;
    for (int k = 0; k < 12 && !hit; k++) hit = segBox(b, A[k], B[k], 0.f, &t, &in);
    if (hit) fl |= CS_IN_CAR;
    if (!b->own && segBox(b, pivot, eye, 0.f, &t, &in) && !in) fl |= CS_OCC_BODY;
  }
  for (int i = 0; i < s->ncyl; i++) {
    const CsCyl *q = &s->cyl[i]; int hit = 0;
    segCyl(q, eye, eye, 0.f, &t, &in); hit = in;
    for (int k = 0; k < 12 && !hit; k++) hit = segCyl(q, A[k], B[k], 0.f, &t, &in);
    if (hit) fl |= CS_IN_PERSON;
    if (segCyl(q, pivot, eye, 0.f, &t, &in) && !in) fl |= CS_OCC_BODY;
  }
  return fl;
}
