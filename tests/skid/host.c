// Правка Роба 249: следы шин на Маке — тот же код машины, коллизии и следов, что на PSP (viewer/car.c, col.c, skid.c с SKID_HOST),
// уровень build/level.shr. Правила — исполняемый файл PS2 SLES_518.97 (адреса в viewer/skid.c). Ровная земля у спавна уровня 1
// (x 160..240, z 172), курс +x.
//   L) уровень заноса skidLevel по правилу 0x282208 на состояниях машины: покой/накат 0; тормоз на ходу 30 % TopSpeed — 1; газ 0;
//      ручник 0,5; тормоз на 5 % и на 60 % — 0; задний ход 20 км/ч с тормозом (0x281684) — 1, 60 км/ч — 0; занос (slip 1/2) —
//      |поперечная доля|, не меньше 0,5 (и почти вдоль носа); газ с места (пробуксовка 0x280f8c) — 1 − 0,5·доля/BurnoutRange
//   A) резкий тормоз с 15 м/с (45 %): следы есть у всех 4 колёс, лежат на земле (0,02..0,10 м над COL1), альфа участков 127
//      (уровень 1 × 0,5 × 255), начало и конец прозрачные, длина следа колеса — путь торможения до 7 % TopSpeed (±1,5 м)
//   A2) тормоз с 25 м/с (75 %): следы начинаются, когда скорость упала ниже 50 % TopSpeed (±1,5 м)
//   B) накат 15 м/с без газа и тормоза, 2 с — следов нет;  C) газ на 30 % и на 60 % TopSpeed — нет
//   D) старт с места на газу: следы только задних колёс и только пока доля < BurnoutRange (пробуксовка, ~1 м)
//   E) ручник с рулём на 15 м/с (slip 2) — следы есть;  R) задний ход (тормоз с места 2 с) — следы задних колёс
//   F) колёса в воздухе — следов нет
//   Красный: -DSKID_MARKS=0 (прежнее: следов нет) — A, A2, D, E, R падают
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "skid.h"
static ColWorld W; static int fails;
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", n); fails += !ok; }
#define DT (1 / 60.f)

static int quads(void) { int n = 0; float p[4][3]; unsigned char a[4]; for (int i = 0; i < SKID_QUADS; i++) n += skidQuadAt(i, p, a); return n; }
static void place(Car *c, float x, float z, float h) {
  float g; if (!colGround(&W, x, z, 50, -50, &g, 0)) { printf("нет земли %.1f %.1f\n", x, z); exit(2); }
  carInit(c, NULL, &W, x, g, z, h);
  for (int k = 0; k < 30; k++) { CarInput in = {0, 0, 0, 0}; carUpdate(c, &W, &in, DT); }
}
static void step(Car *c, CarInput in) { carUpdate(c, &W, &in, DT); skidCar(0, c, &in, &W); }
static float spd(const Car *c) { return sqrtf(c->vel[0] * c->vel[0] + c->vel[1] * c->vel[1] + c->vel[2] * c->vel[2]); }

// длина и высота следов над землёй по кольцу; альфы
typedef struct { int n; float len, hmin, hmax; int amax, a0; } Marks;
static Marks marks(void) {
  Marks m = {0, 0.f, 9.f, -9.f, 0, 0}; float p[4][3]; unsigned char a[4];
  for (int i = 0; i < SKID_QUADS; i++) {
    if (!skidQuadAt(i, p, a)) continue;
    m.n++;
    float mx0 = (p[0][0] + p[1][0]) * .5f, mz0 = (p[0][2] + p[1][2]) * .5f, mx1 = (p[2][0] + p[3][0]) * .5f, mz1 = (p[2][2] + p[3][2]) * .5f;
    m.len += hypotf(mx1 - mx0, mz1 - mz0);
    for (int k = 0; k < 4; k++) {
      float g; if (colGround(&W, p[k][0], p[k][2], p[k][1] + 1.f, p[k][1] - 3.f, &g, 0)) {
        float h = p[k][1] - g; if (h < m.hmin) m.hmin = h; if (h > m.hmax) m.hmax = h; }
      if (a[k] > m.amax) m.amax = a[k];
      m.a0 += a[k] == 0;
    }
  }
  return m;
}

int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  printf("SKID_MARKS=%d кольцо %d квадов\n", SKID_MARKS, SKID_QUADS);
  const float H = 1.5708f, X0 = 200.f, Z0 = 172.f;
  Car c; float top;

  // ---- L: правило уровня на состояниях
  {
    place(&c, X0, Z0, H); top = c.p.topSpeed; float b;
    CarInput none = {0, 0, 0, 0}, brk = {0, 1, 0, 0}, gas = {1, 0, 0, 0}, eb = {0, 0, 0, 1};
    float l0 = skidLevel(&c, &none, &b);
    carSetSpeed(&c, .3f * top); float l1 = skidLevel(&c, &brk, &b), l2 = skidLevel(&c, &gas, &b), l3 = skidLevel(&c, &none, &b), l3e = skidLevel(&c, &eb, &b);
    carSetSpeed(&c, .05f * top); float l4 = skidLevel(&c, &brk, &b);
    carSetSpeed(&c, .6f * top); float l5 = skidLevel(&c, &brk, &b);
    carSetSpeed(&c, -20.f / 3.6f); float l6 = skidLevel(&c, &brk, &b), l6g = skidLevel(&c, &gas, &b);
    carSetSpeed(&c, -60.f / 3.6f); float l6f = skidLevel(&c, &brk, &b);
    carSetSpeed(&c, .3f * top); c.slip = 1; float l7 = skidLevel(&c, &none, &b);   // занос: любая поперечная доля — не меньше 0,5
    { float s = .3f * top; c.vel[0] = sinf(H) * s * .6f + cosf(H) * s * .8f; c.vel[2] = cosf(H) * s * .6f - sinf(H) * s * .8f; }   // 0,8 поперёк
    float l8 = skidLevel(&c, &none, &b); c.slip = 2; float l9 = skidLevel(&c, &eb, &b);
    carSetSpeed(&c, .3f * top); float l9s = skidLevel(&c, &eb, &b); c.slip = 0;
    carSetSpeed(&c, .02f * top); float bb; float l10 = skidLevel(&c, &gas, &bb);
    printf("  уровни: покой %.2f | 30%%: тормоз %.2f газ %.2f накат %.2f ручник %.2f | 5%% тормоз %.2f | 60%% тормоз %.2f | назад 20 км/ч: "
           "тормоз %.2f газ %.2f, 60 км/ч тормоз %.2f | занос прямо %.2f, 0,8 поперёк %.2f, ручник 0,8 поперёк %.2f, ручник прямо %.2f | "
           "с места газ %.2f (пробуксовка %.2f)\n", l0, l1, l2, l3, l3e, l4, l5, l6, l6g, l6f, l7, l8, l9, l9s, l10, bb);
    check("L: правило уровня заноса 0x282208 (+ пробуксовка 0x280f8c, задний ход 0x281684)",
          l0 == 0.f && l1 == 1.f && l2 == 0.f && l3 == 0.f && fabsf(l3e - .5f) < 1e-3f && l4 == 0.f && l5 == 0.f &&
          l6 == 1.f && l6g == 0.f && l6f == 0.f && fabsf(l7 - .5f) < 1e-3f && fabsf(l8 - .8f) < .02f && fabsf(l9 - .8f) < .02f &&
          fabsf(l9s - .5f) < 1e-3f && bb > .85f && bb <= .9f && l10 == bb);
  }

  // ---- A: резкий тормоз с 15 м/с
  skidClear(1);
  place(&c, X0, Z0, H); carSetSpeed(&c, 15.f);
  for (int k = 0; k < 5; k++) step(&c, (CarInput){0, 0, 0, 0});
  float x0 = c.x, xStop = -1.f; int fr = 0;
  while (spd(&c) > .5f && fr < 600) { step(&c, (CarInput){0, 1, 0, 0}); if (xStop < 0 && spd(&c) < .07f * top) xStop = c.x; fr++; }
  for (int k = 0; k < 10; k++) step(&c, (CarInput){0, 0, 0, 0});
  Marks A = marks(); float brakeLen = xStop - x0;
  printf("  A: тормоз %.1f м до 7%% (%.1f с), квадов %d, длина следов %.1f м (на колесо %.1f), над землёй %.3f..%.3f м, альфа до %d, прозрачных углов %d\n",
         brakeLen, fr * DT, A.n, A.len, A.len / 4.f, A.hmin, A.hmax, A.amax, A.a0);
  check("A: тормоз оставляет следы 4 колёс", A.n >= 4 && A.len > 2.f);
  check("A: следы на земле (0,02..0,10 м над COL1)", A.n > 0 && A.hmin > .02f && A.hmax < .10f);
  check("A: альфа участков 127 (1 × 0,5 × 255), начало и конец прозрачные", A.n > 0 && A.amax == 127 && A.a0 >= 4 * 4);
  check("A: длина следа колеса = путь торможения до 7 % TopSpeed (±1,5 м)", A.n > 0 && fabsf(A.len / 4.f - brakeLen) < 1.5f);

  // ---- A2: тормоз с 25 м/с: следы — только ниже 50 % TopSpeed
  skidClear(1); place(&c, X0 - 30.f, Z0, H); carSetSpeed(&c, 25.f);
  for (int k = 0; k < 5; k++) step(&c, (CarInput){0, 0, 0, 0});
  float xHalfB = -1.f; fr = 0;
  while (spd(&c) > .5f && fr < 600) { step(&c, (CarInput){0, 1, 0, 0}); if (xHalfB < 0 && spd(&c) < .5f * top) xHalfB = c.x; fr++; }
  float xFirst = 1e9f; { float p[4][3]; unsigned char a[4]; for (int i = 0; i < SKID_QUADS; i++) if (skidQuadAt(i, p, a))
    for (int k = 0; k < 4; k++) if (p[k][0] < xFirst) xFirst = p[k][0]; }
  printf("  A2: тормоз с 25 м/с: 50%% TopSpeed на x %.1f, начало следов x %.1f (передние колёса впереди центра на %.1f м)\n", xHalfB, xFirst, c.p.wheelF);
  check("A2: следы торможения — ниже 50 % TopSpeed (0x2822f4)", xHalfB > 0 && xFirst < 1e8f && xFirst > xHalfB - c.p.wheelR - 1.5f && xFirst < xHalfB + c.p.wheelF + 1.5f);

  // ---- B: накат без газа и тормоза
  skidClear(1); place(&c, X0, Z0, H); carSetSpeed(&c, 15.f);
  for (int k = 0; k < 120; k++) step(&c, (CarInput){0, 0, 0, 0});
  int qB = quads(); printf("  B: накат 2 с — квадов %d\n", qB);
  check("B: накат — следов нет", qB == 0);
  // ---- C: газ на 30 % и 60 % TopSpeed
  skidClear(1); place(&c, X0 - 40.f, Z0, H); carSetSpeed(&c, .3f * top);
  for (int k = 0; k < 90; k++) step(&c, (CarInput){1, 0, 0, 0});
  int qC1 = quads();
  skidClear(1); place(&c, X0 - 40.f, Z0, H); carSetSpeed(&c, .6f * top);
  for (int k = 0; k < 90; k++) step(&c, (CarInput){1, 0, 0, 0});
  int qC = quads(); printf("  C: газ 1,5 с на 30%% — квадов %d, на 60%% — %d\n", qC1, qC);
  check("C: газ на ходу — следов нет", qC1 == 0 && qC == 0);

  // ---- D: старт с места на газу: пробуксовка задних колёс
  skidClear(1); place(&c, X0 - 40.f, Z0, H);
  float xB = -1.f, xs = c.x;
  for (int k = 0; k < 300; k++) { step(&c, (CarInput){1, 0, 0, 0}); if (xB < 0 && spd(&c) >= c.p.burnoutRange * top) xB = c.x; }
  Marks D = marks(); int front = 0; float dLo = 1e9f, dHi = -1e9f;
  { float p[4][3]; unsigned char a[4];   // курс +x: задние колёса — на wheelR позади центра, передние — на wheelF впереди
    for (int i = 0; i < SKID_QUADS; i++) if (skidQuadAt(i, p, a)) for (int k = 0; k < 4; k++) {
      if (p[k][0] < dLo) dLo = p[k][0]; if (p[k][0] > dHi) dHi = p[k][0];
      if (p[k][0] > xs - c.p.wheelR + (xB - xs) + 1.f) front++; } }
  printf("  D: старт: BurnoutRange (%.0f%%) через %.1f м, квадов %d, длина следов %.1f м, x следов %.1f..%.1f (задняя ось на старте %.1f), "
         "углов впереди задней оси + путь пробуксовки + 1 м: %d\n", c.p.burnoutRange * 100.f, xB - xs, D.n, D.len, dLo, dHi, xs - c.p.wheelR, front);
  check("D: газ с места — короткие следы пробуксовки задних колёс (0x280f8c, 0x2884f8)",
        D.n >= 1 && D.len > .4f && D.len < 2.f * ((xB - xs) + 1.f) && front == 0);

  // ---- E: ручник с рулём
  skidClear(1); place(&c, X0, Z0, H); carSetSpeed(&c, 15.f);
  for (int k = 0; k < 90; k++) step(&c, (CarInput){0, 0, 1, 1});
  Marks E = marks(); printf("  E: ручник + руль 1,5 с с 15 м/с: квадов %d, длина %.1f м, slip %d\n", E.n, E.len, c.slip);
  check("E: ручник — следы", E.n >= 4 && E.len > 4.f);

  // ---- R: задний ход
  skidClear(1); place(&c, X0, Z0, H);
  for (int k = 0; k < 120; k++) step(&c, (CarInput){0, 1, 0, 0});
  Marks R = marks(); printf("  R: тормоз с места 2 с (задний ход до %.1f км/ч): квадов %d, длина %.1f м\n", spd(&c) * 3.6f, R.n, R.len);
  check("R: задний ход — следы задних колёс (0x281684)", R.n >= 2 && R.len > 2.f);

  // ---- F: в воздухе
  skidClear(1); place(&c, X0, Z0, H);
  c.y += 6.f; carSetSpeed(&c, 15.f);
  for (int k = 0; k < 20; k++) step(&c, (CarInput){0, 1, 0, 1});
  int qF = quads(); printf("  F: в воздухе с тормозом и ручником — квадов %d\n", qF);
  check("F: колёса в воздухе — следов нет", qF == 0);

  printf("RESULT %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
