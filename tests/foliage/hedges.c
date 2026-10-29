// Правка Роба 71 (повтор 01.10): «рядом с домом Гомера ... нормально переехать кусты — всё равно они меня выбрасывают в
// разные стороны». Въезд в НАСТОЯЩИЕ кусты уровня (капсулы материала FOLIAGE из build/level.shr: изгороди l1_hedgeunit —
// данные диска: InstaStatPhys cls 2, physProp 10 = строка ATC eShrub/hit_shrub) на 5/10/15 м/с под углом 0/30/60 градусов
// к нормали, с обеих сторон, со всех лежачих кустов уровня, где по обе стороны есть земля, и отдельно — у дома Гомера
// (старт уровня, кусты в 80 м). Машина на газу, руль прямо, 3 с при 60 кадрах/с.
// Гейт на каждый въезд:
//   подброс  — в полёте, начатом с куста (последняя опора — куст), машина не поднимается выше опоры под собой и верха куста
//              больше чем на HOP_MAX м; вертикальная скорость в таком полёте и в кадре удара о куст боком не больше VY_MAX
//              (езда по твёрдым склонам и уступам газона рядом с изгородью — не куст и не в счёт);
//   выброс   — скорость от куста (по его нормали, назад к месту старта) после касания не больше BACK_MAX м/с (куст не
//              пружина), горизонтальная скорость за GAIN_T с после первого касания не растёт больше чем на GAIN_MAX м/с (куст не разгоняет вбок),
//              курс не уводит больше чем на YAW_MAX градусов (не разворачивает: въезд под 60° к нормали и выравнивание вдоль
//              изгороди — до 60°);
//   низкий куст (верх над землёй с обеих сторон ≤ COL_HUMP), если путь не пересекает забор мира (в l1_terra заборы
//              проложены вдоль многих изгородей — там и в оригинале не проехать), — переезжается: на 10–15 м/с прямо машина за кустом.
// Отрицательный контроль (--negative): тот же прогон с прежней реакцией (FOLIAGE_PREV) обязан упасть.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#define HOP_MAX 1.2f
#define VY_MAX 4.5f
#define BACK_MAX 3.0f
#define GAIN_MAX 2.5f
#define GAIN_T 0.3f
#define YAW_MAX 70.f
static ColWorld w; static Car car; static int trace;
typedef struct { float rise, vy, back, side, yaw, cross, hitV; int hops, hitType, hitMat, revWhy, reverts, fence; unsigned hitIdx; } Run;
static int groundAt(float x, float z, float top, float *g) { return colGround(&w, x, z, top, -100, g, 0); }
static Run drive(const ColCyl *c, float t, int side, float ang, float speed) {
  Run r = {0};
  float axl = hypotf(c->axis[0], c->axis[2]), ux = c->axis[0] / axl, uz = c->axis[2] / axl;
  float nx = -uz * side, nz = ux * side;                         // нормаль куста в сторону машины
  float ca = cosf(ang), sa = sinf(ang), dx = -(nx * ca - nz * sa), dz = -(nz * ca + nx * sa);   // ход машины к кусту
  float top = c->c[1] + c->r;
  float px = c->c[0] + ux * t, pz = c->c[2] + uz * t;             // точка касания на оси куста
  float sx = px - dx * (c->r + 7.f), sz = pz - dz * (c->r + 7.f), g;
  if (!groundAt(sx, sz, top + 1.f, &g) || top - g > 2.5f) { r.cross = -99; return r; }   // нет земли или она глубоко под кустом (уступ, проезд снизу)
  carInit(&car, 0, &w, sx, g, sz, atan2f(dx, dz)); carSetSpeed(&car, speed);
  { float ex = px + dx * (c->r + 4.f), ez = pz + dz * (c->r + 4.f), fx, fz; r.fence = colCrossFence(&w, sx, sz, ex, ez, &fx, &fz); }
  // окно замера: центр машины ближе D к отрезку оси куста (в плане) — остальной мир (стены дальше, склоны) не в счёт
  float D = c->r + car.p.halfL + 1.5f, hl = c->halfLen * axl, h0 = 0.f, v0 = 0.f, tc = -1.f;
  CarInput in = {speed > 0.f ? .6f : 0.f, 0, 0, 0}; int fromFol = 0;
  r.rise = -9.f;
  for (int n = 0; n < 180; n++) {
    carUpdate(&car, &w, &in, 1.f / 60.f);
    float qx = car.x - c->c[0], qz = car.z - c->c[2], u = qx * ux + qz * uz; u = u > hl ? hl : u < -hl ? -hl : u;
    if (car.wallV > r.hitV) { r.hitV = car.wallV; r.hitType = car.wallType; r.hitIdx = car.wallIdx; r.hitMat = car.wallMat; }   // весь проезд
    if (trace && hypotf(qx - ux * u, qz - uz * u) > D) printf("  out t %.2f pos %.2f %.2f %.2f vel %.2f %.2f %.2f wheels %d rev %d why %d pen %.3f\n", n / 60.f, car.x, car.y, car.z, car.vel[0], car.vel[1], car.vel[2], car.wheels, car.reverts, car.revWhy, car.pen);
    if (hypotf(qx - ux * u, qz - uz * u) > D) { if (tc >= 0.f) break; continue; }   // уехал от куста — замер окончен
    if (tc < 0.f) { tc = n / 60.f; v0 = hypotf(car.vel[0], car.vel[2]); h0 = car.h; }
    // подброс считается кусту, если машина на нём (опора под центром — куст, удар о куст в кадре) или летит, оторвавшись от
    // него; уступы газона и насыпи рядом (твёрдая земля) — не куст
    float gy = -1e9f; int gm = COL_MAT_HARD; colGroundMat(&w, car.x, car.z, car.y + .3f, -100, &gy, 0, &gm);
    int onFol = gm == COL_MAT_FOLIAGE || car.foliV > 0.f;
    if (car.grounded) fromFol = onFol; else if (onFol) fromFol = 1;
    if (!car.grounded && fromFol) {                                          // полёт, начатый с куста
      if (car.y - fmaxf(gy, top) > r.rise) r.rise = car.y - fmaxf(gy, top);   // над опорой и верхом куста
      if (car.vel[1] > r.vy) r.vy = car.vel[1];
    }
    if (car.foliV > 0.f && car.vel[1] > r.vy) r.vy = car.vel[1];             // удар о куст боком
    if (trace) printf("  t %.2f pos %.2f %.2f %.2f g %.2f top %.2f vel %.2f %.2f %.2f wheels %d gr %d body %d wall %.1f m%d\n", n / 60.f, car.x, car.y, car.z, gy, top,
                      car.vel[0], car.vel[1], car.vel[2], car.wheels, car.grounded, car.bodyHit, car.wallV, car.wallMat);
    if (car.revWhy) r.revWhy |= car.revWhy;
    float vn = car.vel[0] * nx + car.vel[2] * nz, vh = n / 60.f - tc <= GAIN_T ? hypotf(car.vel[0], car.vel[2]) - v0 : 0.f;
    if (vn > r.back) r.back = vn;
    if (vh > r.side) r.side = vh;
    float dy = fabsf(remainderf(car.h - h0, 6.2831853f)) * 57.29578f; if (dy > r.yaw) r.yaw = dy;
  }
  if (r.rise < -8.f) r.rise = 0.f;
  if (tc < 0.f) r.cross = -98;   // до куста не доехал (упёрся раньше в другое) — не судим
  r.cross = (car.x - px) * dx + (car.z - pz) * dz; r.hops = (int)car.foliageBounces; r.reverts = car.reverts;
  return r;
}
// у изгороди есть забор мира ближе 2.2 м к оси (как у 56 изгородей L1): сквозь неё не проехать и в оригинале
static int fenced(const ColCyl *c) {
  for (unsigned j = 0; j < w.nseg; j++) {
    const ColSeg *G = &w.seg[j]; float dx = G->b[0] - G->a[0], dz = G->b[1] - G->a[1], l2 = dx * dx + dz * dz;
    for (int k = -2; k <= 2; k++) {
      float px = c->c[0] + c->axis[0] * c->halfLen * k / 2.f, pz = c->c[2] + c->axis[2] * c->halfLen * k / 2.f;
      float t = l2 > 0.f ? ((px - G->a[0]) * dx + (pz - G->a[1]) * dz) / l2 : 0.f; t = t < 0.f ? 0.f : t > 1.f ? 1.f : t;
      if (hypotf(px - G->a[0] - dx * t, pz - G->a[1] - dz * t) < 2.2f) return 1;
    }
  }
  return 0;
}
// выехать (принцип доводки п. 4): въезд прямо в куст 12 м/с, 2 с газ (прижат), потом 2.5 с тормоз/задний ход —
// машина отходит от куста хотя бы на ESC_MIN м (не прилипает к изгороди и забору по ней)
#define ESC_MIN 1.5f
static int escapes(const ColCyl *c, int side, float *gone) {
  float axl = hypotf(c->axis[0], c->axis[2]), ux = c->axis[0] / axl, uz = c->axis[2] / axl, nx = -uz * side, nz = ux * side, g;
  float sx = c->c[0] + nx * (c->r + 7.f), sz = c->c[2] + nz * (c->r + 7.f), top = c->c[1] + c->r;
  if (!groundAt(sx, sz, top + 1.f, &g) || top - g > 2.5f) return -1;
  carInit(&car, 0, &w, sx, g, sz, atan2f(-nx, -nz)); carSetSpeed(&car, 12.f);
  CarInput in = {1, 0, 0, 0};
  for (int n = 0; n < 120; n++) carUpdate(&car, &w, &in, 1.f / 60.f);
  float d0 = (car.x - c->c[0]) * nx + (car.z - c->c[2]) * nz;
  if (d0 > c->r + 6.f || d0 < 0.f) return -1;                     // не доехал (упёрся раньше) или переехал куст — не прижат, не судим
  in.throttle = 0; in.brake = 1;
  for (int n = 0; n < 150; n++) carUpdate(&car, &w, &in, 1.f / 60.f);
  *gone = (car.x - c->c[0]) * nx + (car.z - c->c[2]) * nz - d0;
  return *gone >= ESC_MIN;
}
// верх куста над землёй с каждой стороны (по середине оси): < 0 — земли нет (край террасы)
static float above(const ColCyl *c, int side) {
  float axl = hypotf(c->axis[0], c->axis[2]), ux = c->axis[0] / axl, uz = c->axis[2] / axl, g, top = c->c[1] + c->r;
  return groundAt(c->c[0] - uz * side * (c->r + 1.5f), c->c[2] + ux * side * (c->r + 1.5f), top - .01f, &g) ? top - g : -1.f;
}
int main(int argc, char **argv) {
  if (argc < 2) return 2; FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15); if (!data || fread(data, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&w, data + co, ce - co)) return 2;
  const float *hd = (const float *)(data + 12); float hx = hd[6], hz = hd[8];
  int fencedN = 0, stuck = 0, hardN = 0, runs = 0, fails = 0, home = 0, lowN = 0, lowCross = 0, lowRuns = 0; float worst[5] = {0};
  for (unsigned i = 0; i < w.ncyl; i++) {
    const ColCyl *c = &w.cyl[i];
    if (c->pad[0] != 1.f || fabsf(c->axis[1]) > .3f || c->halfLen <= 0.f) continue;   // лежачие кусты (изгороди)
    float e0 = above(c, -1), e1 = above(c, 1);
    int near = hypotf(c->c[0] - hx, c->c[2] - hz) < 80.f; home += near;
    int low = e0 >= 0.f && e1 >= 0.f && e0 <= COL_HUMP && e1 <= COL_HUMP, fence = fenced(c); lowN += low; fencedN += fence;
    for (int side = -1; side <= 1; side += 2) {
      if ((side < 0 ? e0 : e1) < 0.f) continue;                        // с этой стороны не подъехать (терраса)
      for (int ai = 0; ai < 3; ai++) for (int si = 0; si < 3; si++) {
        float ang = ai * 30.f / 57.29578f * (side > 0 ? 1.f : -1.f), sp = 5.f + 5.f * si;
        trace = getenv("HEDGE_TRACE") && (int)i == atoi(getenv("HEDGE_TRACE")) && side == atoi(getenv("HEDGE_SIDE")) && ai == atoi(getenv("HEDGE_A")) && si == atoi(getenv("HEDGE_S"));
        Run r = drive(c, 0.f, side, ang, sp);
        if (r.cross == -99 || r.cross == -98 || r.cross < -(c->r + 6.5f)) { stuck += r.cross != -99; continue; }   // нет земли или машина не сдвинулась со старта (зажата там)
        runs++;
        if (r.hitV > 2.f && r.hitMat == COL_MAT_HARD) { hardN++; continue; }   // сильнейший удар — о твёрдого соседа (стена, забор не у куста): его реакция своя
        int bad = r.rise > HOP_MAX || r.vy > VY_MAX || r.back > BACK_MAX || r.side > GAIN_MAX || r.yaw > YAW_MAX;
        if (low && !fence && !r.fence && ai == 0 && si >= 1) { lowRuns++; if (r.cross > c->r + 1.f) lowCross++; else bad |= 2; }
        if (r.rise > worst[0]) worst[0] = r.rise; if (r.vy > worst[1]) worst[1] = r.vy; if (r.back > worst[2]) worst[2] = r.back;
        if (r.side > worst[3]) worst[3] = r.side; if (r.yaw > worst[4]) worst[4] = r.yaw;
        if (bad || (near && argc > 2)) printf("%s cyl %u (%.1f %.1f) %s side %+d angle %2.0f speed %2.0f: rise %.2f vy %.2f back %.2f gain %.2f yaw %.0f cross %.1f hops %d | hit %.1f t%d #%u m%d rev %d why %d\n",
                                 bad ? "FAIL" : "ok  ", i, c->c[0], c->c[2], low ? "low" : "tall", side, ai * 30.f, sp, r.rise, r.vy, r.back, r.side, r.yaw, r.cross, r.hops, r.hitV, r.hitType, r.hitIdx, r.hitMat, r.reverts, r.revWhy);
        fails += bad != 0;
      }
    }
  }
  int escN = 0, escOk = 0; float escWorst = 1e9f;
  for (unsigned i = 0; i < w.ncyl; i++) {
    const ColCyl *c = &w.cyl[i];
    if (c->pad[0] != 1.f || fabsf(c->axis[1]) > .3f || c->halfLen <= 0.f) continue;
    for (int side = -1; side <= 1; side += 2) {
      float gone = 0.f; int r = escapes(c, side, &gone); if (r < 0) continue;
      escN++; escOk += r; if (gone < escWorst) escWorst = gone;
      if (!r) printf("FAIL cyl %u (%.1f %.1f) side %+d: pinned, backed off only %.2f m\n", i, c->c[0], c->c[2], side, gone);
    }
  }
  printf("escape: %d/%d hedges let the car back off >= %.1f m (worst %.2f m)\n", escOk, escN, ESC_MIN, escWorst);
  fails += escN - escOk;
  printf("hard neighbour first: %d runs, start stuck or blocked before the hedge: %d runs (not judged)\n", hardN, stuck);
  printf("hedges: %d runs (%d by Homer's house), worst rise %.2f vy %.2f back %.2f gain %.2f yaw %.0f; low hedges %d, fenced %d, crossed %d/%d\n",
         runs, home, worst[0], worst[1], worst[2], worst[3], worst[4], lowN, fencedN, lowCross, lowRuns);
  printf("%s hedge approaches, %d failures\n", fails || !home || !runs ? "FAIL" : "PASS", fails);
  colFree(&w); free(data); return fails || !home || !runs;
}
