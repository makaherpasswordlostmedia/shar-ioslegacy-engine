// №879 (Роб 23.10 после TEST50: «можем наехать на машину или заехать под неё — в зависимости от того, едем в горку или с горки; в оригинале
// в NPC врезались»): удар машина-машина на склоне. Плоскость y = g·x (уклон g), машина b стоит (вдоль склона или поперёк), машина a с газом
// въезжает в неё снизу (в горку) или сверху (с горки). Плохо: a в конце на крыше b («наезд»), a проехала сквозь b («проныр»), устойчивое
// проникновение кузовов. Кадр как в полигоне: carUpdate обеих -> carHitCar.
//   tests/carslope/host.sh      EXTRA=-DCARSLOPE879_OLD=1 — прежняя проверка высоты (красный контроль)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"

static int fails;
static void check(const char *name, int ok) { printf("%s %s\n", ok ? "OK" : "FAIL", name); fails += !ok; }

// пересечение кузовов в плане (SAT) и вдоль общей оси «вверх» склона
static float bodyOverlap(const Car *a, const Car *b, float g) {
  CarBox A, B; carBox(a, &A); carBox(b, &B);
  float ax[4][2] = {{A.fx, A.fz}, {-A.fz, A.fx}, {B.fx, B.fz}, {-B.fz, B.fx}}, dx = A.x - B.x, dz = A.z - B.z, hmin = 1e9f;
  for (int k = 0; k < 4; k++) {
    float ux = ax[k][0], uz = ax[k][1];
    float ea = A.hw * fabsf(-A.fz * ux + A.fx * uz) + A.hl * fabsf(A.fx * ux + A.fz * uz);
    float eb = B.hw * fabsf(-B.fz * ux + B.fx * uz) + B.hl * fabsf(B.fx * ux + B.fz * uz);
    float ov = ea + eb - fabsf(dx * ux + dz * uz); if (ov <= 0.f) return 0.f; if (ov < hmin) hmin = ov;
  }
  float n = 1.f / sqrtf(1.f + g * g), s = (-g * (a->x - b->x) + (a->y - b->y)) * n;   // высота a над b поперёк склона
  float v = fminf(s + a->p.bodyHi, b->p.bodyHi) - fmaxf(s + a->p.bodyLo, b->p.bodyLo); if (v <= 0.f) return 0.f;
  return fminf(hmin, v);
}

// -> 0 хорошо; 1 наезд на крышу; 2 проныр сквозь; 3 устойчивое проникновение
static int scene(const ColWorld *w, float g, int fromBelow, float yawB, float speed) {
  Car a, b; const float dt = 1 / 60.f; float dir = fromBelow ? 1.f : -1.f;
  carInit(&b, NULL, w, 0, 0, 0, yawB); for (int k = 0; k < 60; k++) { CarInput in = {0}; in.handbrake = 1.f; carUpdate(&b, w, &in, dt); }
  float x0 = -dir * 11.f; carInit(&a, NULL, w, x0, g * x0, 0, dir > 0 ? 1.5708f : -1.5708f);
  for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&a, w, &in, dt); }
  carSetSpeed(&a, speed);
  int pen = 0, worst = 0, roofT = 0, contact = 0; float maxOv = 0, minGap = 1e9f;
  for (int t = 0; t < 300; t++) {
    CarInput ia = {0}, ib = {0}; ia.throttle = 1.f; ib.handbrake = 1.f;   // тормоз у стоящей = задний ход: только ручник
    carUpdate(&a, w, &ia, dt); carUpdate(&b, w, &ib, dt);
    if (carHitCar(&a, &b, w)) contact++;
    float ov = bodyOverlap(&a, &b, g); if (ov > maxOv) maxOv = ov;
    pen = ov > .15f ? pen + 1 : 0; if (pen > worst) worst = pen;
    float n = 1.f / sqrtf(1.f + g * g), s = (-g * (a.x - b.x) + (a.y - b.y)) * n;
    if (s > .9f && fabsf(a.x - b.x) < 2.5f) roofT++;
    float gap = dir * (b.x - a.x); if (gap < minGap) minGap = gap;
  }
  int through = dir * (a.x - b.x) > 2.f && fabsf(a.z - b.z) < 1.5f;   // центр a ушёл за центр b по ходу на той же линии (не объехал вбок)
  int res = roofT > 30 ? 1 : through ? 2 : worst >= 12 ? 3 : 0;
  printf("уклон %3.0f%% %-8s b %-7s %4.1f м/с: контакт %3d кадров, на крыше %3d, сквозь %d, перекрытие %.2f м (%d подряд), a (%.1f %.1f) b (%.1f %.1f) -> %s\n",
         g * 100, fromBelow ? "в горку" : "с горки", yawB == 0.f ? "поперёк" : "вдоль", speed, contact, roofT, through, maxOv, worst, a.x, a.y, b.x, b.y,
         res == 0 ? "удар" : res == 1 ? "НАЕЗД" : res == 2 ? "ПРОНЫР" : "ПРОНИКНОВЕНИЕ");
  return res;
}

int main(void) {
  int bad = 0, n = 0;
  const float G[4] = {0.f, .15f, .25f, .35f};
  for (int i = 0; i < 4; i++) {
    float g = G[i];
    static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } m;
    memset(&m, 0, sizeof m); memcpy(m.h.magic, "COL1", 4); m.h.ox = m.h.oz = -100; m.h.cell = 200; m.h.W = m.h.H = 1; m.h.ntri = 2; m.h.nref = 2;
    float ny = 1.f / sqrtf(1 + g * g), nx = -g * ny;
    m.t[0] = (ColTri){{-100, -100 * g, -100}, {100, 100 * g, 100}, {100, 100 * g, -100}, {nx, ny, 0}};
    m.t[1] = (ColTri){{-100, -100 * g, -100}, {-100, -100 * g, 100}, {100, 100 * g, 100}, {nx, ny, 0}};
    m.start[1] = 2; m.refs[0] = 0; m.refs[1] = 1;
    ColWorld w; if (colInit(&w, &m, sizeof m)) return 2;
    for (int up = 1; up >= 0; up--) for (int yb = 0; yb < 2; yb++) for (int sp = 0; sp < 2; sp++) {
      int r = scene(&w, g, up, yb ? 1.5708f : 0.f, sp ? 18.f : 8.f); bad += r != 0; n++; }
  }
  check("на склоне 0–35 % машина врезается в машину: ни наезда на крышу, ни проныра сквозь, ни проникновения", bad == 0);
  printf("RESULT: %s (%d из %d сцен плохо)\n", fails ? "FAIL" : "OK", bad, n);
  return fails ? 1 : 0;
}
