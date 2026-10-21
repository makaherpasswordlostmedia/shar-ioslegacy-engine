// Машина на машине (пункт 8 docs/handoff/LOOP_TERMINAL.md): крыша другой машины — опора, в том числе едущей; без
// проваливания. Плоская земля, кадр как в полигоне: carUpdate обеих → carHitCar → замер. Сцены:
//   падение на стоящую машину с 1, 3 и 6 м над крышей (курс верхней 0° и 30°)
//   падение с 3 м на едущую 8 м/с
//   прыжок: верхняя летит 12 м/с с высоты 3 м над землёй прямо на крышу стоящей
// «Проникновение кузовов»: пересечение в плане (SAT) и по высоте кузовов глубже 0.15 м 12 тиков подряд.
//   tests/carstack/host.sh      CAR_C=… CAR_H_DIR=… EXTRA=-DCARHIT2 — старая версия (отрицательный контроль)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"

static int fails;
static void check(const char *name, int ok) { printf("%s %s\n", ok ? "OK" : "FAIL", name); fails += !ok; }

static float bodyOverlap(const Car *a, const Car *b) {
  CarBox A, B; carBox(a, &A); carBox(b, &B);
  float ax[4][2] = {{A.fx, A.fz}, {-A.fz, A.fx}, {B.fx, B.fz}, {-B.fz, B.fx}}, dx = A.x - B.x, dz = A.z - B.z, hmin = 1e9f;
  for (int k = 0; k < 4; k++) {
    float ux = ax[k][0], uz = ax[k][1];
    float ea = A.hw * fabsf(-A.fz * ux + A.fx * uz) + A.hl * fabsf(A.fx * ux + A.fz * uz);
    float eb = B.hw * fabsf(-B.fz * ux + B.fx * uz) + B.hl * fabsf(B.fx * ux + B.fz * uz);
    float ov = ea + eb - fabsf(dx * ux + dz * uz); if (ov <= 0.f) return 0.f; if (ov < hmin) hmin = ov;
  }
  float a0 = a->y + a->p.bodyLo, a1 = a->y + a->p.bodyHi, b0 = b->y + b->p.bodyLo, b1 = b->y + b->p.bodyHi;
  float v = fminf(a1, b1) - fmaxf(a0, b0); if (v <= 0.f) return 0.f;
  return fminf(hmin, v);
}

static void hit(Car *a, Car *b, const ColWorld *w) {
#ifdef CARHIT2
  (void)w; carHitCar(a, b);
#else
  carHitCar(a, b, w);
#endif
}

// одна сцена: 4 с по 1/60; верхняя a, нижняя b. -> 1, если устойчивое проникновение; *onTop — a в конце на крыше b
static int scene(const ColWorld *w, const char *name, float h, float yawA, float vB, float vAx, float startDx, int *onTop) {
  Car a, b; const float dt = 1 / 60.f;
  carInit(&b, NULL, w, 0, 0, 0, 0); for (int k = 0; k < 30; k++) { CarInput in = {0}; carUpdate(&b, w, &in, dt); }
  carInit(&a, NULL, w, startDx, 0, 0, yawA); a.y = b.y + b.p.bodyHi + h; a.ry = a.y;
  if (vB > 0) { carSetSpeed(&b, vB); a.vel[0] = b.vel[0]; a.vel[2] = b.vel[2]; }   // верхняя летит вместе с нижней
  if (vAx != 0) { a.vel[2] = 0; a.vel[0] = vAx; }                     // прыжок: полёт вдоль x к нижней
  int pen = 0, worst = 0, bad = 0; float maxOv = 0;
  for (int t = 0; t < 240; t++) {
    CarInput ia = {0}, ib = {0}; if (vB > 0) ib.throttle = b.v < vB ? 1.f : 0.f;
    carUpdate(&a, w, &ia, dt); carUpdate(&b, w, &ib, dt);
    hit(&a, &b, w);
    float ov = bodyOverlap(&a, &b); if (ov > maxOv) maxOv = ov;
    pen = ov > 0.15f ? pen + 1 : 0; if (pen > worst) worst = pen;
    if (!isfinite(a.y) || !isfinite(b.y)) { bad = 1; break; }
  }
  float dx = a.x - b.x, dz = a.z - b.z;
  *onTop = a.y > b.y + 1.0f && hypotf(dx, dz) < 2.5f;
  printf("%-28s a (%.2f %.2f %.2f) b (%.2f %.2f %.2f) max overlap %.3f m, persistent %d ticks, on top %d, a v %.1f b v %.1f\n",
         name, a.x, a.y, a.z, b.x, b.y, b.z, maxOv, worst, *onTop, a.v, b.v);
  return bad || worst >= 12;
}

int main(void) {
  static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } g = {0};
  memcpy(g.h.magic, "COL1", 4); g.h.ox = g.h.oz = -100; g.h.cell = 200; g.h.W = g.h.H = 1; g.h.ntri = 2; g.h.nref = 2;
  g.t[0] = (ColTri){{-100, 0, -100}, {100, 0, 100}, {100, 0, -100}, {0, 1, 0}};
  g.t[1] = (ColTri){{-100, 0, -100}, {-100, 0, 100}, {100, 0, 100}, {0, 1, 0}};
  g.start[1] = 2; g.refs[0] = 0; g.refs[1] = 1;
  ColWorld w; if (colInit(&w, &g, sizeof g)) return 2;
  int pens = 0, stay = 0, top;
  const float H[3] = {1, 3, 6};
  for (int i = 0; i < 3; i++) for (int k = 0; k < 2; k++) {
    char n[64]; snprintf(n, sizeof n, "drop %.0fm yaw %d", H[i], k * 30);
    pens += scene(&w, n, H[i], k * 0.5236f, 0, 0, 0, &top); stay += top;
  }
  pens += scene(&w, "drop 3m on moving 8 m/s", 3, 0, 8, 0, 0, &top); int rides = top;
  pens += scene(&w, "jump 12 m/s onto roof", 1.35f, 1.5708f, 0, 12, -9, &top);
  check("no persistent car-car penetration (drops, moving, jump)", pens == 0);
  check("a car dropped on a standing car ends on its roof", stay == 6);
  check("a car dropped on a moving car rides on its roof", rides);
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails ? 1 : 0;
}
