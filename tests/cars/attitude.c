// №406 (09.10, Роб: «машины в поворотах отрываются, переворачиваются»; аудит 09.10: после 406 крен внутрь и нос вверх на тормозе).
// Положение кузова порта против уже снятых записей PS2 (эталон tests/cars/attitude_ps2.tsv, tools/twins/attitude_ref.py).
// Ровная площадка, тот же carUpdate, что в игре, 50 Гц как запись. Проверки:
//   A крен наружу у всех машин диска (15 м/с, руль ±0,5): ось вверх кузова отклонена от центра поворота;
//   B famil_v крен на м/с² бокового ускорения (15 м/с, руль 0,55 и 0,7): наружу и не больше, чем у PS2 (наибольшая корзина);
//   C famil_v полный тормоз с 20 м/с: нос вниз и клевок не больше, чем у PS2 (наибольшая корзина);
//   B и C односторонние: у порта крен и клевок мягче PS2 (ступица, см. docs/handoff/ФИЗИКА_СВЕРКА_PS2_2026-10-09.md) — печатается доля;
//   D famil_v газ на скорости 6–19 м/с: нос не поднимается (у PS2 на скорости приседания нет: −0,05 °/(м/с²));
//   E famil_v полный тормоз 12,5 → 3 м/с: темп в пределах заездов PS2 от v > 10 м/с;
//   G famil_v полный руль со средней скоростью отсчётов PS2 (14,3 м/с): рыскание в квартилях PS2, скольжение не больше p90.
//   cc -std=c11 -O2 -I viewer tests/cars/attitude.c viewer/car.c viewer/col.c -lm -o attitude && ./attitude [tests/cars/attitude_ps2.tsv]
// Код выхода — число проваленных проверок. Красные: -DCAR_TYRE_HUB_OLD=1 (406: A, C), -DCAR_TYRE_LEVER_OLD=1 (Fable: B),
// -DCAR_BRAKE_PLUS3_OLD=1 (E), -DCAR_GAS_GRIP_OLD=1 (G).
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "car.h"
#include "carparams.h"
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fl;
static ColWorld W;
static float rollMax = -1e9f, rollMed[8], brkLo = 1e9f, brkHi = -1e9f, decLo = 1e9f, decHi = -1e9f, squatPs2 = 0.f, yawM, yawQ1, yawQ3, slip90, yawV = 15.f;
static int nRoll;
static void ref(const char *path) {
  FILE *f = fopen(path, "r"); if (!f) { printf("нет %s\n", path); exit(99); }
  char l[512];
  while (fgets(l, sizeof l, f)) {
    char k[32], b[32]; int n; float v; if (l[0] == '#' || sscanf(l, "%31s %31s %d %f", k, b, &n, &v) != 4) continue;
    if (!strcmp(k, "roll_grad")) { if (v > rollMax) rollMax = v; if (nRoll < 8) rollMed[nRoll++] = v; }
    else if (!strcmp(k, "pitch_brake")) { if (v < brkLo) brkLo = v; if (v > brkHi) brkHi = v; }
    else if (!strcmp(k, "pitch_gas")) squatPs2 = v;
    else if (!strcmp(k, "brake_run") && atof(b) > 10.f) { v = -v; if (v < decLo) decLo = v; if (v > decHi) decHi = v; }
    else if (!strcmp(k, "yaw_15")) { if (!strcmp(b, "median")) yawM = v; else if (!strcmp(b, "q1")) yawQ1 = v; else if (!strcmp(b, "q3")) yawQ3 = v; else if (!strcmp(b, "v_median")) yawV = v; }
    else if (!strcmp(k, "slip_15")) slip90 = v;
  }
  fclose(f);
}
static void start(Car *c, const char *name, float v) {
  CarParams p; carParamsFor(name, &p); carInit(c, &p, &W, 0, 0, 0, 0);
  CarInput in = {1, 0, 0, 0}; for (int f = 0; f < 50 * 20 && hypotf(c->vel[0], c->vel[2]) < v; f++) carUpdate(c, &W, &in, 1 / 50.f);
}
// поворот с удержанием скорости: средний наклон оси вверх к центру (°, + внутрь), боковое ускорение, рыскание, скольжение
static void turn(const char *name, float v, float steer, float *tilt, float *alat, float *yaw, float *slip) {
  Car c; start(&c, name, v); CarInput in = {1, 0, steer, 0};
  float va[3]; memcpy(va, c.vel, sizeof va); float hp = c.h; double st = 0, sa = 0, sy = 0, ss = 0; int n = 0;
  for (int f = 0; f < 100; f++) {
    in.throttle = hypotf(c.vel[0], c.vel[2]) < v ? 1.f : 0.f; carUpdate(&c, &W, &in, 1 / 50.f);
    float ax = (c.vel[0] - va[0]) * 50.f, az = (c.vel[2] - va[2]) * 50.f; memcpy(va, c.vel, sizeof va);
    float dh = remainderf(c.h - hp, 6.2831853f); hp = c.h;
    const float *q = c.q; float ux = 2.f * (q[1] * q[2] - q[0] * q[3]), uz = 2.f * (q[2] * q[3] + q[0] * q[1]), al = hypotf(ax, az);
    float sl = fabsf(remainderf(atan2f(c.vel[0], c.vel[2]) - c.h, 6.2831853f)) * 57.2958f; if (sl > 90.f) sl = 180.f - sl;
    if (f >= 50 && al > 1.f) { st += asinf(fmaxf(-1.f, fminf(1.f, (ux * ax + uz * az) / al))) * 57.2958f; sa += al; sy += fabsf(dh) * 50.f * 57.2958f; ss += sl; n++; }
  }
  *tilt = n ? st / n : 0.f; *alat = n ? sa / n : 0.f; *yaw = n ? sy / n : 0.f; *slip = n ? ss / n : 0.f;
}
int main(int argc, char **argv) {
  if (getenv("ROLLG")) carRollGain = (float)atof(getenv("ROLLG"));
  ref(argc > 1 ? argv[1] : "tests/cars/attitude_ps2.tsv");
  memset(&fl, 0, sizeof fl); memcpy(fl.h.magic, "COL1", 4); fl.h.ox = fl.h.oz = -2000; fl.h.cell = 4000; fl.h.W = fl.h.H = 1; fl.h.ntri = fl.h.nref = 2;
  fl.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}};
  fl.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  fl.start[1] = 2; fl.refs[0] = 0; fl.refs[1] = 1; if (colInit(&W, &fl, sizeof fl)) return 99;
  int fails = 0;
  // A
  { int runs = 0, in = 0; float worst = -1e9f; const char *wn = "";
    for (int m = 0; m < CAR_CONS; m++) for (int s = -1; s <= 1; s += 2) {
      float t, a, y, sl; turn(carCons[m].name, 15.f, .5f * s, &t, &a, &y, &sl); if (a < 3.f) continue;
      runs++; if (t > 0.05f) in++; if (t > worst) { worst = t; wn = carCons[m].name; } }
    int ok = in == 0; fails += !ok;
    printf("%s A крен наружу: заездов %d, внутрь %d (наибольший наклон к центру %+.2f° у %s)\n", ok ? "ok  " : "FAIL", runs, in, worst, wn); }
  // B
  { float t1, a1, t2, a2, y, sl; turn("famil_v", 15.f, .55f, &t1, &a1, &y, &sl); turn("famil_v", 15.f, .7f, &t2, &a2, &y, &sl);
    float g = -.5f * (t1 / a1 + t2 / a2); int ok = g > 0.f && g <= rollMax; fails += !ok;
    printf("%s B famil_v крен %.3f °/(м/с²) наружу при %.1f–%.1f м/с² (PS2 по корзинам %.3f %.3f %.3f %.3f, не больше %.3f; доля от PS2 %.0f %%)\n", ok ? "ok  " : "FAIL",
           g, a1, a2, rollMed[0], rollMed[1], rollMed[2], rollMed[3], rollMax, 100.f * g / rollMax); }
  // C + E
  { Car c; start(&c, "famil_v", 20.f); float p0 = c.pitch; CarInput in = {0, 1, 0, 0}; double sa = 0, sp = 0; int n = 0;
    float v0 = hypotf(c.vel[0], c.vel[2]);
    for (int f = 0; f < 200 && c.v > 6.f; f++) { float vb = c.v; carUpdate(&c, &W, &in, 1 / 50.f); if (f >= 8) { sa += (c.v - vb) * 50.f; sp += (c.pitch - p0) * 57.2958f; n++; } }
    float r = n ? sp / sa : 0.f; int ok = r > 0.f && r <= brkHi; fails += !ok; (void)v0;
    printf("%s C famil_v тормоз: тангаж/замедление %.3f °/(м/с²), нос %s (PS2 %.3f…%.3f, нос вниз; доля от PS2 %.0f…%.0f %%)\n", ok ? "ok  " : "FAIL", r, r > 0 ? "вниз" : "ВВЕРХ", brkLo, brkHi, 100.f * r / brkHi, 100.f * r / brkLo);
    start(&c, "famil_v", 12.5f); float vs = c.v; int f = 0; for (; f < 200 && c.v > 3.f; f++) carUpdate(&c, &W, &in, 1 / 50.f);
    float d = (vs - c.v) / (f / 50.f); ok = d >= decLo && d <= decHi; fails += !ok;
    printf("%s E famil_v полный тормоз %.1f → 3 м/с: %.1f м/с² (PS2 %.1f…%.1f)\n", ok ? "ok  " : "FAIL", vs, d, decLo, decHi); }
  // D
  { Car c; CarParams p; carParamsFor("famil_v", &p); carInit(&c, &p, &W, 0, 0, 0, 0); CarInput in = {0, 0, 0, 0};
    for (int f = 0; f < 50; f++) carUpdate(&c, &W, &in, 1 / 50.f);
    float p0 = c.pitch; double sa = 0, sp = 0; in.throttle = 1;
    for (int f = 0; f < 1500 && c.v < 19.f; f++) { float vb = c.v; carUpdate(&c, &W, &in, 1 / 50.f); if (c.v > 6.f) { sa += (c.v - vb) * 50.f; sp += (c.pitch - p0) * 57.2958f; } }
    float r = sp / sa; int ok = r <= 0.f; fails += !ok;
    printf("%s D famil_v газ на скорости: тангаж/ускорение %+.3f °/(м/с²) (PS2 %+.3f — нос не поднимается)\n", ok ? "ok  " : "FAIL", r, squatPs2); }
  // G: поворот на полном руле со скоростью отсчётов PS2
  { float t, a, y, sl; turn("famil_v", yawV, 1.f, &t, &a, &y, &sl);
    int ok = y >= yawQ1 && y <= yawQ3 && sl <= slip90; fails += !ok;
    printf("%s G famil_v полный руль %.1f м/с — рыскание %.1f °/с, скольжение %.1f° (PS2 медиана %.1f, квартили %.1f…%.1f, скольжение p90 %.1f°)\n",
           ok ? "ok  " : "FAIL", yawV, y, sl, yawM, yawQ1, yawQ3, slip90); }
  // файл rollps2 (ROLLG=0,22): крен famil_v не меньше 85 % медианы PS2 и рыскание остаётся в квартилях (без файла проверки B/G выше — прежние)
  if (carRollGain > 0.f) {
    float tilt, alat, yaw, slip; turn("famil_v", 15.f, .55f, &tilt, &alat, &yaw, &slip); float grad = alat > 0.1f ? -tilt / alat : 0.f;
    float t2, a2, y2, s2; turn("famil_v", yawV, 1.f, &t2, &a2, &y2, &s2);
    int ok = grad >= 0.17f && y2 >= yawQ1;
    fails += !ok; printf("%s R rollps2: famil_v крен %.3f °/(м/с²) наружу (PS2 до %.3f, нужно ≥ 0,17), рыскание на полном руле %.1f °/с (квартили PS2 %.1f…%.1f)\n", ok ? "ok  " : "FAIL", grad, rollMax, y2, yawQ1, yawQ3);
  }
  printf("attitude: %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails;
}
