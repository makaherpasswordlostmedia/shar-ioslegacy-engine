// ДОБИВКА 14, частные машины (правки Роба 354, 358, 368): по проверке на каждую машину, тот же carUpdate, что в игре.
//   A honor_v (354, главная машина Барта L2) и все машины диска: колесо подвески в покое там же, где колесо модели. Центр колеса
//     модели — сфера колеса CollisionObject диска (car_wheel_collision.h) на суставе w0..w3, над землёй на s.y + lift; центр колеса
//     подвески порта в покое — на wheelRad. Проверка для каждой машины с колёсами на одной высоте (79 из 87): |wheelRad − (s.y + lift)|
//     ≤ 1 см на каждом колесе и предел хода lim = эта высота × SuspensionLimit ± 1 мм ([PS2] ps2-native-wheel-field-binding: предел
//     = радиус × SuspensionLimit, famil_v 0,26620 = 0,380285 × 0,7). Красный: -DCAR_WHEEL_RADIUS_MESH_OLD=1 (радиус — полувысота
//     меша; у honor_v это куб-заглушка 0,2605: колесо на 8,2 см ниже колеса модели, ход 0,156 вместо 0,206).
//   B lisa_v и plowk_v (358: «Malibu Stacy очень лёгкая — переворачивается», «Plow King переворачивается на резких поворотах
//     влево-вправо»): ровная площадка — полный руль с газом и с ручником (как cornering.c) и змейка полным рулём 0,4–1,3 с, на газу
//     и с ручником; уровень 3 (LEVEL3) — те же 300 постановок по карте (seed 777): разгон 3 с, затем змейка/ручник/полруля 9 с
//     (заезд, где машина упала больше чем на 10 м — с крыши или обрыва, — печатается и не считается). Проверка: ни одного переворота. Красный: физика до 406 (-DCAR_TYRE_LEVER_OLD=1 -DCAR_WEEBLE_GROUND_OLD=1): lisa_v
//     переворачивается (на ровном с ручником и на карте L3).
//   C bart_v (368, L6: «прыжок с трамплина — удар отбрасывает машину сильно задом вверх»): трамплин L6 jumpzone (JMP1, зона
//     с именем "jumpzone"; заезд против оси ax зоны, 45 м разгона, 70/90/110 км/ч, руль на линию до отрыва). После посадки 2,5 с
//     тангаж не ниже −45° (нет «задом вверх»), не перевернулась. Красный: -DCAR_AIR_PITCH_OLD=1 (прежнее затухание в полёте:
//     нос +13° замирает, машина садится задом на кромку, на 90 км/ч закручивает до −90°).
//   cc -std=c11 -O2 -I viewer tests/cars/car_specific.c viewer/car.c viewer/col.c -lm -o car_specific
//   ./car_specific LEVEL3.shr LEVEL6.shr   -> строки по машинам, итог «RESULT A ok|FAIL B ok|FAIL C ok|FAIL»; код = число провалов
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "carparams.h"
#include "car_inertia.h"
#include "car_wheel_collision.h"

static float wrapf(float a) { while (a > 3.14159265f) a -= 6.2831853f; while (a < -3.14159265f) a += 6.2831853f; return a; }
static float upY(const Car *c) { return 1.f - 2.f * (c->q[1] * c->q[1] + c->q[3] * c->q[3]); }
static int loadLevel(const char *path, ColWorld *w) {
  FILE *f = fopen(path, "rb"); if (!f) return -1;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15L);
  if (!data || fread(data, 1, size, f) != (size_t)size) { fclose(f); return -1; }
  fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  return colInit(w, data + co, ce - co) ? -2 : 0;   // данные уровня живут до конца процесса
}
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } floorData;
static ColWorld flat;
static void flatInit(void) {
  memset(&floorData, 0, sizeof floorData); memcpy(floorData.h.magic, "COL1", 4);
  floorData.h.ox = floorData.h.oz = -2000; floorData.h.cell = 4000; floorData.h.W = floorData.h.H = 1; floorData.h.ntri = floorData.h.nref = 2;
  floorData.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}};
  floorData.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  floorData.start[1] = 2; floorData.refs[0] = 0; floorData.refs[1] = 1;
  colInit(&flat, &floorData, sizeof floorData);
}

// ---------------------------------------------------------------- A
static int checkA(void) {
  int bad = 0, worse = 0, n = 0, uneq = 0;
  printf("A  колесо подвески против колеса модели в покое (м): машина, радиус подвески, центры колёс над землёй, отклонение, ход/норма\n");
  for (unsigned k = 0; k < sizeof carBodyPhysics / sizeof *carBodyPhysics; k++) {
    const char *name = carBodyPhysics[k].name; CarParams p;
    if (!carParamsFor(name, &p) || p.wheelCollision[0][3] <= 0.f) continue;
    Car c; carInit(&c, &p, &flat, 0, 0, 0, 0);
    float h[4], lo = 1e9f, hi = -1e9f, mean = 0.f, gap = 0.f;
    for (int i = 0; i < 4; i++) { h[i] = p.wheelCollision[i][1] + p.modelLift; lo = fminf(lo, h[i]); hi = fmaxf(hi, h[i]); mean += h[i] * .25f; }
    if (hi - lo > .01f) { uneq++; continue; }   // колёса перед/зад на разной высоте — у порта одно значение на машину, не проверяется
    for (int i = 0; i < 4; i++) gap = fmaxf(gap, fabsf(p.wheelRad - h[i]));
    float limWant = mean * p.suspensionLimit, limGap = fabsf(c.lim - limWant);
    int ok = gap <= 0.01f && limGap <= 0.001f; n++; worse += !ok;
    if (!strcmp(name, "honor_v") || !ok)
      printf("   %-9s r %.4f колёса %.4f %.4f %.4f %.4f (сфера %.4f) откл %.4f ход %.4f/%.4f %s\n", name, p.wheelRad, h[0], h[1], h[2], h[3],
             p.wheelCollision[0][3], gap, c.lim, limWant, ok ? "ok" : "ВНЕ");
    bad += !ok;
  }
  printf("A  машин с колёсами на одной высоте %d, вне допуска %d (справочно: на разной высоте %d)\n", n, worse, uneq);
  return bad;
}

// ---------------------------------------------------------------- B
static int flatRuns(const char *name, int *two) {
  CarParams p; carParamsFor(name, &p); const float dt = 1.f / 30.f; int flips = 0, frames = 0; *two = 0;
  for (int mode = 0; mode < 2; mode++) {   // полный руль: газ / ручник (как cornering.c)
    Car c; carInit(&c, &p, &flat, 0, 0, 0, 0); CarInput in = {1.f, 0.f, 0.f, 0.f};
    for (int f = 0; f < 300; f++) carUpdate(&c, &flat, &in, dt);
    in.steer = 1.f; in.handbrake = (float)mode; int fl = 0, r0 = c.rights;
    for (int f = 0; f < 180; f++) { carUpdate(&c, &flat, &in, dt); fl |= upY(&c) < 0.f; *two += c.wheels <= 2; frames++; }
    flips += fl || c.rights > r0;
  }
  const float per[] = {0.4f, 0.6f, 0.8f, 1.0f, 1.3f};
  for (int pi = 0; pi < 5; pi++) for (int mode = 0; mode < 2; mode++) {   // змейка: руль влево-вправо, газ / ручник в начале перекладки
    Car c; carInit(&c, &p, &flat, 0, 0, 0, 0); CarInput in = {1.f, 0.f, 0.f, 0.f};
    for (int f = 0; f < 300; f++) carUpdate(&c, &flat, &in, dt);
    int fl = 0, r0 = c.rights;
    for (int f = 0; f < 240; f++) {
      float t = f * dt; in.steer = fmodf(t, 2 * per[pi]) < per[pi] ? 1.f : -1.f; in.handbrake = mode && fmodf(t, per[pi]) < .25f ? 1.f : 0.f;
      carUpdate(&c, &flat, &in, dt); fl |= upY(&c) < 0.f; *two += c.wheels <= 2; frames++;
    }
    flips += fl || c.rights > r0;
  }
  *two = 100 * *two / frames;
  return flips;
}
static unsigned rs; static float rnd(void) { rs = rs * 1103515245u + 12345u; return (rs >> 8) / 16777216.f; }
static int levelRuns(const char *name, const ColWorld *w, int *runs, int *falls) {
  CarParams p; carParamsFor(name, &p); const float dt = 1 / 60.f; int flips = 0; rs = 777; *runs = 0; *falls = 0;
  for (int k = 0; k < 300; k++) {
    float x = w->ox + rnd() * w->W * w->cell, z = w->oz + rnd() * w->H * w->cell, h = rnd() * 6.2832f, g, per = .5f + rnd();
    int mode = k % 3;
    if (!colGround(w, x, z, 200.f, -200.f, &g, 0)) continue;
    Car c; carInit(&c, &p, w, x, g + 1.f, z, h);
    for (int i = 0; i < 10; i++) { CarInput in = {0}; carUpdate(&c, w, &in, dt); }
    if (c.wheels < 4) continue;
    int fl = 0, r0 = c.rights; float y0 = c.y, ymin = c.y;
    for (int f = 0; f < 60 * 12; f++) {
      float t = f * dt; CarInput in = {1.f, 0.f, 0.f, 0.f};
      if (t > 3.f) {
        if (mode == 0) in.steer = fmodf(t, 2 * per) < per ? 1.f : -1.f;
        else if (mode == 1) { in.steer = 1.f; in.handbrake = fmodf(t, 2.f) < .3f; }
        else in.steer = fmodf(t, 2 * per) < per ? .6f : -.6f;
      }
      carUpdate(&c, w, &in, dt); fl |= upY(&c) < 0.f; if (c.y < ymin) ymin = c.y;
    }
    if (y0 - ymin > 10.f) { (*falls)++; continue; }   // съехала с крыши/обрыва и упала больше 10 м: это падение, не поворот
    (*runs)++; flips += fl || c.rights > r0;
  }
  return flips;
}
static int checkB(const ColWorld *l3) {
  const char *cars[] = {"lisa_v", "plowk_v", "famil_v"}; int bad = 0;
  for (int i = 0; i < 3; i++) {
    int two, runs = 0, falls = 0, ff = flatRuns(cars[i], &two), fl = l3 ? levelRuns(cars[i], l3, &runs, &falls) : 0;
    int ok = ff == 0 && fl == 0;
    printf("B  %-8s ровно: переворотов %d из 12, на двух колёсах %d%% кадров | L3: переворотов %d из %d (падений с высоты, не в счёт: %d) %s%s\n",
           cars[i], ff, two, fl, runs, falls, ok ? "ok" : "FAIL", i == 2 ? " (справочно)" : "");
    if (i < 2) bad += !ok;
  }
  return bad;
}

// ---------------------------------------------------------------- C
static int checkC(const ColWorld *w) {
  if (!w) { printf("C  нет уровня 6\n"); return 1; }
  const ColZone *Z = 0; for (uint32_t i = 0; i < w->nzone; i++) if (!strcmp(w->zone[i].name, "jumpzone")) Z = &w->zone[i];
  if (!Z) { printf("C  на уровне нет зоны jumpzone\n"); return 1; }
  CarParams p; carParamsFor("bart_v", &p); const float dt = 1 / 60.f; int bad = 0;
  float dx = -Z->ax[0], dz = -Z->ax[2], l = hypotf(dx, dz); dx /= l; dz /= l;
  printf("C  bart_v, L6 jumpzone (%.1f, %.1f, %.1f), курс %.1f°\n", Z->c[0], Z->c[1], Z->c[2], atan2f(dx, dz) * 57.2958f);
  for (int vi = 0; vi < 3; vi++) {
    float vt = (70.f + 20.f * vi) / 3.6f, x0 = Z->c[0] - dx * 45.f, z0 = Z->c[2] - dz * 45.f, g;
    if (!colGround(w, x0, z0, Z->c[1] + 15.f, Z->c[1] - 25.f, &g, 0)) { printf("C  нет земли на старте\n"); return 1; }
    Car c; carInit(&c, &p, w, x0, g + 1.f, z0, atan2f(dx, dz));
    for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&c, w, &in, dt); }
    carSetSpeed(&c, vt * .8f);
    float airT = 0.f, tLand = -1.f, pTouch = 0.f, pMin = 0.f, flight = 0.f; int took = 0, flip = 0;
    for (int fr = 0; fr < 600; fr++) {
      float along = (c.x - Z->c[0]) * dx + (c.z - Z->c[2]) * dz; CarInput in = {0};
      in.throttle = hypotf(c.vel[0], c.vel[2]) < vt ? 1.f : 0.f;
      if (!took) { float a = along + 15.f, tx = Z->c[0] + dx * a, tz = Z->c[2] + dz * a;
        in.steer = fmaxf(-1.f, fminf(1.f, -2.f * wrapf(atan2f(tx - c.x, tz - c.z) - c.h))); }
      carUpdate(&c, w, &in, dt);
      float t = (fr + 1) * dt, pitch = c.pitch * 57.2958f;
      if (c.wheels == 0 && !c.grounded) { airT += dt; if (airT > .3f) took = 1; }
      else { if (took && tLand < 0.f) { tLand = t; pTouch = pitch; flight = airT; } airT = 0.f; }
      if (tLand >= 0.f && t - tLand < 2.5f) { if (pitch < pMin) pMin = pitch; flip |= upY(&c) < 0.f; }
    }
    int ok = tLand >= 0.f && pMin >= -45.f && !flip;
    printf("C  %3.0f км/ч: полёт %.2f с, тангаж при касании %+6.1f°, наименьший за 2,5 с после %+6.1f°%s %s\n", vt * 3.6f, flight, pTouch, pMin,
           flip ? " ПЕРЕВЕРНУЛАСЬ" : "", ok ? "ok" : "FAIL");
    bad += !ok;
  }
  return bad > 0;
}

int main(int argc, char **argv) {
  flatInit();
  static ColWorld l3, l6; int h3 = argc > 1 && loadLevel(argv[1], &l3) == 0, h6 = argc > 2 && loadLevel(argv[2], &l6) == 0;
  if (argc > 1 && !h3) printf("нет уровня %s\n", argv[1]);
  int a = checkA(), b = checkB(h3 ? &l3 : 0), c = checkC(h6 ? &l6 : 0);
  printf("RESULT A %s B %s C %s\n", a ? "FAIL" : "ok", b ? "FAIL" : "ok", c ? "FAIL" : "ok");
  return a + (b > 0) + c;
}
