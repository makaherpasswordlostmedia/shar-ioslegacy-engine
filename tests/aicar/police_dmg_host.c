// Правка Роба 280 (04.10: «полицейская машина от трёх ударов взрывается»): машина погони L1 (cPolice, Pursuit\\L1cop.con,
// SetHitPoints 0.5) на ровной площадке; машина Гомера (famil_v, HitPoints 3) таранит её в бок на 20 м/с до разбития.
// Правило порта: полиция — машина ИИ, урон машина-машина × CAR_HIT_DMG_K, как трафик (близнец В14). Проверка: доля урона от тарана против машины миссии ≈ 0,45 (закон трафика).
// Красный (tests/aicar/police_dmg.sh): -DPOLICE_DMG_OLD=1 — полный урон машин миссий
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "msncar.h"
static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-4s %s  %s\n", n, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fx;
static ColWorld W;
static void ram(Car *t, float v) {   // машина Гомера в 12 м слева, лоб в бок цели; 2 с
  Car a; carInit(&a, 0, &W, t->x - 12.f, 0.f, t->z, 1.5707963f); a.p.hitPoints = 3.f; carSetSpeed(&a, v);
  CarInput in = {1, 0, 0, 0}, none = {0, 0, 0, 1};
  for (int f = 0; f < 120; f++) { carUpdate(&a, &W, &in, 1.f / 60.f); carUpdate(t, &W, &none, 1.f / 60.f); carHitCar(&a, t, &W); }
}
static int hitsToBreak(Car *t, int max) {
  int k = 0; float x = t->x, z = t->z;
  for (; k < max && !t->destroyed; k++) { t->x = x; t->z = z; memset(t->vel, 0, sizeof t->vel); memset(t->w, 0, sizeof t->w); ram(t, 20.f); }
  return t->destroyed ? k : -1;
}
int main(void) {
  memcpy(fx.h.magic, "COL1", 4); fx.h.ox = fx.h.oz = -60; fx.h.cell = 120; fx.h.W = fx.h.H = 1; fx.h.ntri = 2; fx.h.nref = 2;
  fx.t[0] = (ColTri){{-60, 0, -60}, {60, 0, 60}, {60, 0, -60}, {0, 1, 0}};
  fx.t[1] = (ColTri){{-60, 0, -60}, {-60, 0, 60}, {60, 0, 60}, {0, 1, 0}};
  fx.start[1] = 2; fx.refs[0] = 0; fx.refs[1] = 1;
  if (colInit(&W, &fx, sizeof fx)) { printf("FAIL: мир\n"); return 1; }
  char d[200]; static MsnCars M; mcInit(&M); float pos[3] = {0.f, 0.f, 0.f};
  McCar *c = mcSpawn(&M, &W, 0, "cPolice", pos, 0.f, 1, "chase", "Pursuit\\L1cop.con", "");
  if (!c) { printf("FAIL: полицейская не поставлена\n"); return 1; }
  McCar *ref = mcSpawn(&M, &W, 0, "cPolice2", (float[3]){30.f, 0.f, 0.f}, 0.f, 1, "chase", "Pursuit\\L1cop.con", "");   // эталон: полный урон машин миссий
#ifndef POLICE_DMG_OLD
  c->car.hitDmgK = 0.f;   // как viewer/game_msn.c gameMsnPolice (правка 280): урон как у трафика (× CAR_HIT_DMG_K)
#endif
  if (!ref) { printf("FAIL: эталон не поставлен\n"); return 1; }
  ram(&c->car, 20.f); ram(&ref->car, 20.f);
  float r = ref->car.damage > 0.f ? c->car.damage / ref->car.damage : -1.f;
  snprintf(d, sizeof d, "полицейская L1 (HitPoints %.2f), один таран 20 м/с: урон %.3f, у машины миссии %.3f (доля %.2f — закон трафика 0,45)",
           c->car.p.hitPoints, c->car.damage, ref->car.damage, r);
  check("cop", r > .35f && r < .55f, d);
  { Car *t = &c->car; t->damage = 0.f; t->destroyed = 0; int k = hitsToBreak(t, 30); printf("INFO таранов 20 м/с до разбития: %d (у оригинала — близнец В47)\n", k); }
  printf("RESULT %s провалов %d\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
