// Гейт правки 355 (остов): синтетический мир — плоский пол COL1 400×400 м, без данных игры. Машина famil_v по умолчанию.
//  A — разбита и горит (до взрыва, 3 с): с полным газом стоит (< 0,3 м) — правка 199 не сломана;
//  B — остов после взрыва едет медленно: полный газ 5 с -> 2..CAR_HUSK_TOP + 0,3 м/с и уехал > 5 м [PS2 близнец: 4–5 м/с];
//  C — посадка: в горящую не сесть (homerCanEnter 0, hc.dead), в остов — можно (1, hc.husk);
//  E — остов не игрока (трафик, миссии): как прежде — газ не слушает, сесть нельзя;
//  D — оставленная своя машина не «призрак»: машина трафика, въехавшая в неё, вытолкнута и перешла в физику, своя не сдвинулась.
// Красный: -DCAR_HUSK_OLD=1 обязан упасть на B и C.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "homer.h"
#include "traffic.h"
static int fails;
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", n); fails += !ok; }

static uint32_t colBuf[1024];
static int flatWorld(ColWorld *W) {   // COL1: 1×1 клетка 400 м, два треугольника пола y = 0
  unsigned char *b = (unsigned char *)colBuf; memset(colBuf, 0, sizeof colBuf);
  ColHdr h; memset(&h, 0, sizeof h); memcpy(h.magic, "COL1", 4); h.ox = -200.f; h.oz = -200.f; h.cell = 400.f; h.W = h.H = 1; h.ntri = 2; h.nref = 2;
  memcpy(b, &h, 48);
  ColTri t[2] = {{{-200, 0, -200}, {-200, 0, 200}, {200, 0, 200}, {0, 1, 0}}, {{-200, 0, -200}, {200, 0, 200}, {200, 0, -200}, {0, 1, 0}}};
  memcpy(b + 48, t, sizeof t);
  uint32_t cs[2] = {0, 2}, refs[2] = {0, 1};
  memcpy(b + 48 + 96, cs, 8); memcpy(b + 48 + 96 + 8, refs, 8);
  return colInit(W, b, 48 + 96 + 16);
}
static void run(Car *c, const ColWorld *W, float thr, float secs) {
  for (int k = 0; k < (int)(secs * 60.f + .5f); k++) { CarInput in = {thr, 0, 0, 0}; carUpdate(c, W, &in, 1 / 60.f); }
}

int main(void) {
  static ColWorld W; if (flatWorld(&W)) { printf("FAIL мир\n"); return 2; }
  Car c; carInit(&c, NULL, &W, 0.f, 0.f, 0.f, 0.f); c.huskDrive = 1; run(&c, &W, 0.f, 1.f);   // машина игрока (game.c gameCarStep)
  // A
  c.damage = 1.f; c.destroyed = 1; float x0 = c.x, z0 = c.z;
  run(&c, &W, 1.f, 2.8f);
  check("A: горящая (до взрыва) с полным газом стоит", hypotf(c.x - x0, c.z - z0) < .3f && !carBoomed(&c));
  // C (до взрыва)
  static Homer H; memset(&H, 0, sizeof H); H.state = HS_FOOT;
  HomerCar hc; memset(&hc, 0, sizeof hc); homerCarFrom(&hc, &c, .7f);
  float door[3] = {hc.m[12] + hc.m[0] * hc.door[0] + hc.m[8] * hc.door[1], 0.f, hc.m[14] + hc.m[2] * hc.door[0] + hc.m[10] * hc.door[1]};
  H.x = door[0]; H.y = c.y; H.z = door[2];
  check("C1: в горящую не сесть", hc.dead && !homerCanEnter(&H, &hc));
  // B
  run(&c, &W, 0.f, 0.5f); x0 = c.x; z0 = c.z;
  check("B0: взорвалась (остов)", carBoomed(&c));
  homerCarFrom(&hc, &c, .7f);
  check("C2: в остов сесть можно (без двери и ириса)", !hc.dead && hc.husk && homerCanEnter(&H, &hc));
  run(&c, &W, 1.f, 5.f); float d = hypotf(c.x - x0, c.z - z0);
  printf("   остов: %.2f м/с, %.1f м за 5 с\n", fabsf(c.v), d);
  check("B1: остов едет медленно (2..CAR_HUSK_TOP+0,3 м/с, > 5 м)", fabsf(c.v) > 2.f && fabsf(c.v) < CAR_HUSK_TOP + .3f && d > 5.f);
  // E: остов НЕ игрока (трафик, стоянка, машина миссии) — как прежде: вход не слушает (газ — стоит), сесть нельзя
  { Car o; carInit(&o, NULL, &W, -50.f, 0.f, -50.f, 0.f); run(&o, &W, 0.f, .5f); o.damage = 1.f; o.destroyed = 1; run(&o, &W, 0.f, 3.5f);
    float ox = o.x, oz = o.z; run(&o, &W, 1.f, 3.f); HomerCar ho; memset(&ho, 0, sizeof ho); homerCarFrom(&ho, &o, .7f);
    check("E: остов не игрока — газ не слушает, сесть нельзя (как прежде)", carBoomed(&o) && hypotf(o.x - ox, o.z - oz) < .3f && ho.dead && !ho.husk); }
  // D: машина трафика въехала в оставленную
  static Traffic T; static TrHeader hd; memset(&T, 0, sizeof T); memset(&hd, 0, sizeof hd); T.hd = &hd; T.maxCars = 1;
  Car own; carInit(&own, NULL, &W, 50.f, 0.f, 50.f, 0.f); run(&own, &W, 0.f, .5f);
  Car keep = own; TrCar *tc = &T.car[0]; tc->mode = TRM_DRIVE;
  carInit(&tc->car, NULL, &W, 50.f + 1.2f, 0.f, 50.f, 0.f); run(&tc->car, &W, 0.f, .2f);
  float d0 = hypotf(tc->car.x - own.x, tc->car.z - own.z);
  int hits = 0; for (int k = 0; k < 30; k++) { hits += trafficHitStill(&T, &W, &own); run(&tc->car, &W, 0.f, 1 / 60.f); }
  float d1 = hypotf(tc->car.x - own.x, tc->car.z - own.z);
  printf("   трафик: %.2f -> %.2f м, ударов %d\n", d0, d1, hits);
  check("D: трафик упёрся в оставленную и вытолкнут, своя не сдвинулась", hits > 0 && d1 > d0 + .3f && tc->mode == TRM_PHYS &&
        own.x == keep.x && own.z == keep.z);
  printf("RESULT %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
