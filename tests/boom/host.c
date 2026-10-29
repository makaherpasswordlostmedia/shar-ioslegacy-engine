// Правка Роба 199 (03.10): взрыв машины как у оригинала (близнец tools/twins/boom.py, PS2 50 к/с): после смертельного удара
// машина стоит и горит, Гомер вылетает через ~0,75 с (правка 147, tests/eject147), взрыв и остов — через 3,0 с после удара.
// Проверки (машина уровня, мир build/level.shr, Мак, CPU): A — до 2,9 с взрыва нет (carBoomed 0), к 3,1 с — есть; B — газ и руль
// разбитая машина не слушает (сместилась < 0,3 м за 3 с с полным газом); C — у целой часы не идут. Красный: -DCAR_BOOM_DELAY=0
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W; static int fails;
static void check(const char *n, int ok) { printf("%s %s\n", ok ? "ok" : "FAIL", n); fails += !ok; }
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  Car c; float g; if (!colGround(&W, 220.f, 172.f, 50.f, -50.f, &g, 0)) return 2;
  carInit(&c, NULL, &W, 220.f, g, 172.f, 1.5708f);
  for (int k = 0; k < 60; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }
  // C: целая машина — часы стоят
  for (int k = 0; k < 120; k++) { CarInput in = {1, 0, 0}; carUpdate(&c, &W, &in, 1 / 60.f); }
  check("C: у целой машины часы взрыва не идут", c.deadT == 0.f && !carBoomed(&c));
  carSetSpeed(&c, 0.f); for (int k = 0; k < 60; k++) { CarInput in = {0}; carUpdate(&c, &W, &in, 1 / 60.f); }   // стоит (удар остановил)
  // разбита: урон 1 (как смертельный удар), дальше полный газ и руль
  c.damage = 1.f; c.destroyed = 1; float x0 = c.x, z0 = c.z, tBoom = -1.f;
  int early = 0; float xb = c.x, zb = c.z;
  for (int k = 1; k <= 300; k++) {
    CarInput in = {1, 0, 1.f}; carUpdate(&c, &W, &in, 1 / 60.f);
    float t = k / 60.f;
    if (carBoomed(&c) && tBoom < 0.f) { tBoom = t; xb = c.x; zb = c.z; }   // правка 355: остов после взрыва едет — меряем до взрыва
    if (t < 2.9f && carBoomed(&c)) early = 1;
  }
  if (tBoom < 0.f) { xb = c.x; zb = c.z; }
  float moved = hypotf(xb - x0, zb - z0);
  printf("  взрыв через %.2f с после удара (оригинал 3,04 с), сместилась %.2f м\n", tBoom, moved);
  check("A: до 2,9 с взрыва нет, к 3,1 с — есть (как у PS2)", !early && tBoom > 2.9f && tBoom < 3.1f);
  check("B: разбитая машина (до взрыва) не слушает газ и руль", moved < .3f);
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails != 0;
}
