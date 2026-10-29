// Автопилот теста (слово Роба, TEST14 раздел 5): машина едет по сети дорог трафика как игрок — обычная скорость, повороты, торможение перед машиной впереди,
// застрял > 3 с — задний ход и новый путь. Чистый C: PSP-сборка теста (flag drive, main_loop.h) и хост (tools/bots/pilot.c) гоняют один и тот же код.
// Только под флагом сценария теста, в игре не активен. Путь — mcPlan (тот же, что у машин миссий).
#ifndef SMKPILOT_H
#define SMKPILOT_H
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include "car.h"
#include "props.h"
#include "stateprops.h"
#include "traffic.h"
#include "msncar.h"
// №618 «мозги» теста: обход препятствий (люди, машины, пропы) боковым шагом и возврат на путь. PILOT_AVOID_OLD=1 — прежнее поведение (красный контроль)
static int spAvoidOff(void) { static int v = -1; if (v < 0) { const char *e = getenv("PILOT_AVOID_OLD"); v = e && e[0] == '1'; } return v; }
typedef struct { float x, z, r; } SmkObs;
#define SMK_OBS_MAX 48
// круги препятствий в радиусе range от (px, pz): пешеходы 0.5, машины трафика и стоянки 2.2 (кроме skipCar), пропы не ниже minH по полуразмеру
static int spGather(const Traffic *t, const Props *pr, const StateProps *sp, float px, float pz, float range, float minH, const Car *skipCar, SmkObs *o) {
  int n = 0; float R2 = range * range;
#define SP_ADD(X, Z, RR) do { float dx_ = (X) - px, dz_ = (Z) - pz; if (n < SMK_OBS_MAX && dx_ * dx_ + dz_ * dz_ < R2 && dx_ * dx_ + dz_ * dz_ > 0.04f) { o[n].x = (X); o[n].z = (Z); o[n].r = (RR); n++; } } while (0)
  if (t && t->hd) {
    for (int j = 0; j < t->maxPeds; j++) { const TrPed *d = &t->ped[j]; if (d->mode == TRP_OFF) continue; SP_ADD(d->x, d->z, .5f); }
    for (int j = 0; j < t->maxCars; j++) { const TrCar *c = &t->car[j]; if (c->mode == TRM_OFF || &c->car == skipCar) continue; SP_ADD(c->car.x, c->car.z, 2.2f); }
    for (int j = 0; j < t->npark; j++) { const TrParked *c = &t->park[j]; if (c->gone || &c->car == skipCar) continue; SP_ADD(c->car.x, c->car.z, 2.2f); }
  }
  if (pr && pr->st) for (unsigned j = 0; j < pr->ninst; j++) { const PropState *s = &pr->st[j]; if (s->hidden) continue;
    float hh = fmaxf(s->hx, s->hz); if (s->hy < minH || hh < .15f) continue; SP_ADD(s->x, s->z, fminf(hh, 3.f)); }
  if (sp && sp->inst && sp->run) for (unsigned j = 0; j < sp->ninst; j++) { const SpInst *I = &sp->inst[j]; const SpType *T = &sp->type[I->type]; if (!sp->run[j].alive || T->kind) continue;
    float hh = fmaxf(T->h[0], T->h[2]); if (T->h[1] < minH || hh < .15f) continue; SP_ADD(I->x + T->c[0], I->z + T->c[2], fminf(hh, 3.f)); }   // стейтпропы (столбы, ящики, заборчики): центр без поворота, радиус с запасом
#undef SP_ADD
  return n;
}
// ближайшее препятствие на ходу: фронт (fx, fz) единичный, look — дальность, halfW — полуширина ходока. -> 1 и точка обхода (*ax, *az) сбоку от препятствия; *dist — до него; *side — запомненная сторона
static int spAvoidAim(const SmkObs *o, int n, float px, float pz, float fx, float fz, float look, float halfW, float *side, float *ax, float *az, float *dist) {
  float best = 1e30f, bl = 0, br = 0;
  for (int i = 0; i < n; i++) { float dx = o[i].x - px, dz = o[i].z - pz, ah = dx * fx + dz * fz, lat = dx * fz - dz * fx;   // lat — вдоль n = (fz, -fx)
    if (ah <= 0.f || ah > look + o[i].r || fabsf(lat) > o[i].r + halfW) continue; if (ah < best) { best = ah; bl = lat; br = o[i].r; } }
  if (best > 1e29f) return 0;
  float sg = fabsf(bl) > .25f ? (bl > 0 ? -1.f : 1.f) : (*side != 0.f ? *side : 1.f); *side = sg;
  float lat = bl + sg * (br + halfW + .5f);
  *ax = px + fx * (best + .5f) + fz * lat; *az = pz + fz * (best + .5f) - fx * lat; *dist = best - br; return 1;
}
typedef struct {
  float clock, lastSX, lastSZ, lastST; int stuckRep, behind;   // №618: часы, где и когда застряла в прошлый раз, повторы на одном месте, цель позади
  const Props *props; const StateProps *sp; float side;   // №618: пропы для обхода (может быть NULL), запомненная сторона обхода
  float route[MC_ROUTE][3]; int n, seg, offroad;
  float goal[3]; int haveGoal;
  float planT, stuckT, backT, backSteer, dist, lx, lz, vcap, ignoreT, waitT;
  unsigned rng; int stuckN, plans, goals, why;
} SmkPilot;
static unsigned spRnd(SmkPilot *p) { p->rng = p->rng * 1664525u + 1013904223u; return p->rng >> 8; }
static void smkPilotInit(SmkPilot *p, unsigned seed, float vcap) { memset(p, 0, sizeof *p); p->rng = seed * 2654435761u + 1u; p->vcap = vcap > 1.f ? vcap : 16.f; }
static int spPickGoal(SmkPilot *p, const Traffic *t, const Car *c) {   // случайная точка полосы на 80–500 м
  if (!t || !t->hd || !t->hd->nRoad) return 0;
  for (int k = 0; k < 80; k++) {   // №618: первые 40 попыток — с учётом «цель позади», остальные — любая цель
    unsigned r = spRnd(p) % t->hd->nRoad; const TrRoad *R = &t->road[r]; if (!R->nPt) continue;
    const TrPt *q = &t->pt[R->firstPt + spRnd(p) % R->nPt]; float d = hypotf(q->x - c->x, q->z - c->z);
    if (d < 80.f || d > 500.f) continue;
    if (p->behind && k < 40 && !spAvoidOff() && (q->x - c->x) * sinf(c->h) + (q->z - c->z) * cosf(c->h) > -20.f) continue;   // после повторного застревания цель — позади машины, а не снова в ту же стену
    p->goal[0] = q->x; p->goal[1] = q->y; p->goal[2] = q->z; p->haveGoal = 1; p->goals++; p->behind = 0; return 1; }
  return 0;
}
// один шаг: заполняет in (руль -1..1 в соглашении CarInput.steer/стика бота, газ, тормоз, ручник). dt — секунды кадра
static void smkPilotStep(SmkPilot *p, const Traffic *t, const Car *c, float dt, CarInput *in) {
  memset(in, 0, sizeof *in); p->why = 0; p->clock += dt;
  float v = c->v, moved = hypotf(c->x - p->lx, c->z - p->lz); p->dist += moved; p->lx = c->x; p->lz = c->z;
  if (p->backT > 0.f) { p->backT -= dt; in->brake = 1.f; in->throttle = 0.f; in->steer = p->backSteer; if (v < .5f) { in->brake = 1.f; } p->planT = 0.f; p->n = 0; return; }
  if (fabsf(v) < 1.f) p->stuckT += dt; else p->stuckT = 0.f;
  if (p->stuckT > (spAvoidOff() ? 3.f : 2.f)) { p->stuckT = 0.f; p->stuckN++; p->backT = 1.4f; p->backSteer = (p->stuckN & 1) ? 1.f : -1.f; p->haveGoal = 0; p->n = 0; p->ignoreT = 8.f;
    if (!spAvoidOff()) {   // №618: задний ход с рулём 1,5 с; на том же месте повторно — дольше и с новой целью позади, а не в ту же стену
      p->stuckRep = (hypotf(c->x - p->lastSX, c->z - p->lastSZ) < 12.f && p->clock - p->lastST < 60.f) ? p->stuckRep + 1 : 0;
      p->lastSX = c->x; p->lastSZ = c->z; p->lastST = p->clock; p->backT = fminf(3.5f, 1.5f + .7f * p->stuckRep); p->behind = p->stuckRep >= 1; }
    return; }   // 8 с после застревания — стоящую впереди машину не пережидаем, а объезжаем/толкаем
  if (!p->haveGoal || hypotf(p->goal[0] - c->x, p->goal[2] - c->z) < 14.f) { if (!spPickGoal(p, t, c)) { p->why = 1; return; } p->n = 0; }
  if (p->n == 0 || (p->planT -= dt) <= 0.f) {   // цель, до которой пути нет, — другая цель в этом же кадре (до 6 попыток)
    for (int k = 0; k < 6; k++) { p->n = mcPlan(t, c->x, c->y, c->z, c->h, p->goal, 1, p->route, MC_ROUTE, &p->offroad); p->plans++; if (p->n > 0) break; p->n = 0; if (!spPickGoal(p, t, c)) { p->why = 2; return; } }
    p->seg = 0; p->planT = 3.f; if (p->n <= 0) { p->why = 3; return; } }
  float L = 5.f + .35f * fabsf(v);
  while (p->seg < p->n - 1 && hypotf(p->route[p->seg + 1][0] - c->x, p->route[p->seg + 1][2] - c->z) < L) p->seg++;
  const float *tg = p->route[p->seg < p->n - 1 ? p->seg + 1 : p->n - 1];
  float av[3] = {0, 0, 0}; int avoiding = 0, imminent = 0;   // №618: препятствие на ходу — цель сдвигается в сторону от него, дальше путь возвращается сам
  if (!spAvoidOff()) { SmkObs ob[SMK_OBS_MAX]; int no = spGather(t, p->props, p->sp, c->x, c->z, 14.f + 1.2f * fabsf(v), .6f, c, ob); float ax_, az_, ad_;
    if (spAvoidAim(ob, no, c->x, c->z, sinf(c->h), cosf(c->h), 6.f + fabsf(v), 1.4f, &p->side, &ax_, &az_, &ad_)) { float fx_ = sinf(c->h), fz_ = cosf(c->h), lat = fmaxf(-4.f, fminf(4.f, (ax_ - c->x) * fz_ - (az_ - c->z) * fx_));   // цель пути сдвигается вбок на lat, а не заменяется
        av[0] = tg[0] + fz_ * lat; av[2] = tg[2] - fx_ * lat; tg = av; avoiding = 1; imminent = ad_ < 3.f; } }
  float e = atan2f(tg[0] - c->x, tg[2] - c->z) - c->h; while (e > 3.14159f) e -= 6.28318f; while (e < -3.14159f) e += 6.28318f;
  float turn = 0.f;
  if (p->seg + 2 < p->n) { const float *a = p->route[p->seg], *b = p->route[p->seg + 1], *d = p->route[p->seg + 2];
    float a1 = atan2f(b[0] - a[0], b[2] - a[2]), a2 = atan2f(d[0] - b[0], d[2] - b[2]), dd = a2 - a1; while (dd > 3.14159f) dd -= 6.28318f; while (dd < -3.14159f) dd += 6.28318f; turn = fabsf(dd); }
  float vt = p->vcap; if (turn > .5f) vt = fminf(vt, 11.f); if (fabsf(e) > .6f) vt = fminf(vt, 8.f);
  if (avoiding) vt = fminf(vt, 7.f);
  in->steer = fmaxf(-1.f, fminf(1.f, -e * 2.2f));
  if (v < vt) in->throttle = 1.f; else if (v > vt + 3.f) in->brake = .6f;
  // машина или пешеход впереди: притормозить (объезд — по полосам плана)
  if (p->ignoreT > 0.f) p->ignoreT -= dt;
  int hit_ = 0;
  if (t && t->hd && p->ignoreT <= 0.f && !avoiding) for (int j = 0; j < t->maxCars; j++) { const TrCar *o = &t->car[j]; if (o->mode == TRM_OFF) continue;
    float dx = o->car.x - c->x, dz = o->car.z - c->z, fx = sinf(c->h), fz = cosf(c->h), ahead = dx * fx + dz * fz, side = fabsf(dx * fz - dz * fx);
    if (ahead > 0.f && ahead < 6.f + 1.2f * fabsf(v) && side < 2.6f) { in->throttle = 0.f; in->brake = 1.f; hit_ = 1; p->why = 4; break; } }
  if (avoiding && imminent && v > 2.f) { in->throttle = 0.f; in->brake = .5f; p->why = 5; }
  if (hit_ && fabsf(v) < 1.f) { if ((p->waitT += dt) > 2.f) { p->waitT = 0.f; p->ignoreT = 8.f; } } else p->waitT = 0.f;   // стоящую впереди машину пережидаем 2 с, потом объезжаем/толкаем
}

// ---- пешком: Гомер идёт по замкнутым путям пешеходов трафика (тротуар); стоит на месте > 2 с — разворот по пути; цель шага — точка пути, стик от камеры считает вызывающий
typedef struct { int path, idx, dir, stuckN, inited; float rx, rz, lx, lz, stuckT, dist; const Props *props; const StateProps *sp; float side; int sideSwaps; } SmkWalk;   // props/side/sideSwaps — №618
static void smkWalkInit(SmkWalk *w) { memset(w, 0, sizeof *w); w->dir = 1; }
static const float *swPt(const Traffic *t, int p, int k) { const TrPath *P = &t->path[p]; return t->pathPt + 3 * (P->first + (uint32_t)((k % (int)P->n + (int)P->n) % (int)P->n)); }
// -> 1, если есть цель (*tx, *tz)
static int smkWalkStep(SmkWalk *w, const Traffic *t, float hx, float hz, float dt, float *tx, float *tz) {
  if (!t || !t->hd || !t->hd->nPath) return 0;
  if (!w->inited) {   // ближайшая точка любого пути
    float bd = 1e30f; for (uint32_t p = 0; p < t->hd->nPath; p++) { const TrPath *P = &t->path[p]; if (!P->n) continue;
      for (uint32_t k = 0; k < P->n; k++) { const float *q = swPt(t, (int)p, (int)k); float d = (q[0] - hx) * (q[0] - hx) + (q[2] - hz) * (q[2] - hz); if (d < bd) { bd = d; w->path = (int)p; w->idx = (int)k; } } }
    w->inited = 1; w->lx = w->rx = hx; w->lz = w->rz = hz; }
  w->dist += hypotf(hx - w->lx, hz - w->lz); w->lx = hx; w->lz = hz;
  if (hypotf(hx - w->rx, hz - w->rz) > .8f) { w->rx = hx; w->rz = hz; w->stuckT = 0.f; }
  else if ((w->stuckT += dt) > 2.f) { w->stuckT = 0.f; w->stuckN++;
    if (!spAvoidOff() && (w->sideSwaps++ & 1) == 0) w->side = w->side != 0.f ? -w->side : 1.f;   // №618: первый раз — другая сторона обхода, второй — разворот по пути
    else { w->dir = -w->dir; w->idx += 2 * w->dir; } }
  const float *q = swPt(t, w->path, w->idx);
  for (int k = 0; k < 8 && hypotf(q[0] - hx, q[2] - hz) < 1.6f; k++) { w->idx += w->dir; q = swPt(t, w->path, w->idx); }
  *tx = q[0]; *tz = q[2];
  if (!spAvoidOff()) { float dx = q[0] - hx, dz = q[2] - hz, L = hypotf(dx, dz); if (L > .01f) { SmkObs ob[SMK_OBS_MAX]; int no = spGather(t, w->props, w->sp, hx, hz, 6.f, .3f, NULL, ob); float ax, az, ad;   // сфера впереди по ходу, шаг в сторону, возврат на путь
      if (spAvoidAim(ob, no, hx, hz, dx / L, dz / L, 3.f, .5f, &w->side, &ax, &az, &ad)) { *tx = ax; *tz = az; } } }
  return 1;
}
#endif
