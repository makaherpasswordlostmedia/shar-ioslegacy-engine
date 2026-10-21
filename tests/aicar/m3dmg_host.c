// Ночь ботов 02.10→03.10: m3 Office Spaced не проходится — цель тарана smith_v (AddStageVehicle с Missions\level01\M3dest.con,
// SetHitPoints 1.5) после правки 176 получала от машины Гомера урон × CAR_HIT_DMG_K (0,45, правило про трафик: оракул В14,
// минивэн трафика цел после 14 таранов) и не разбивалась, пока Смитерс не доезжал до конца пути (бот: с × 1 m3 без трафика
// пройдена за 265 с, с × 0,45 — нет). Машина миссии через viewer/msncar.c (mcSpawn, ходовые .con из таблицы диска) на ровной
// площадке; машина Гомера famil_v (HitPoints 3) таранит её в бок на 20 м/с, пока не разбита:
//   msn   — цель m3 разбита не позже 5-го тарана (как до правки 176)
//   traf  — машина не миссии (трафик, игрок: урон × CAR_HIT_DMG_K) с той же прочностью от одного такого тарана получает долю
//           0,35–0,55 урона цели — правка 176 для трафика на месте
// Красный (tests/aicar/m3dmg.sh): -DMC_HIT_DMG_TRAFFIC=1 — машине миссии урон как у трафика (× 0,45)
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
  char d[200];
  static MsnCars M; mcInit(&M);
  float pos[3] = {0.f, 0.f, 0.f};
  McCar *c = mcSpawn(&M, &W, 0, "smith_v", pos, 0.f, 1, "NULL", "Missions\\level01\\M3dest.con", "smithers");
  if (!c) { printf("FAIL: машина миссии не поставлена\n"); return 1; }
  int k = hitsToBreak(&c->car, 12);
  snprintf(d, sizeof d, "цель m3 smith_v (M3dest.con, HitPoints %.1f): таранов 20 м/с до разбития %d", c->car.p.hitPoints, k);
  check("msn", c->car.p.hitPoints > 1.4f && c->car.p.hitPoints < 1.6f && k > 0 && k <= 5, d);
  { McCar *c2 = mcSpawn(&M, &W, 0, "smith_v2", (float[3]){30.f, 0.f, 0.f}, 0.f, 1, "NULL", "Missions\\level01\\M3dest.con", "smithers");
    Car van; carInit(&van, 0, &W, -30.f, 0.f, 0.f, 0.f); van.p = c2 ? c2->car.p : van.p;   // трафик: hitDmgK = 0 -> CAR_HIT_DMG_K
    if (c2) { ram(&c2->car, 20.f); ram(&van, 20.f); }
    float r = c2 && c2->car.damage > 0.f ? van.damage / c2->car.damage : -1.f;
    snprintf(d, sizeof d, "один таран 20 м/с, прочность 1.5: урон цели миссии %.3f, машины не миссии %.3f (доля %.2f)", c2 ? c2->car.damage : 0.f, van.damage, r);
    check("traf", r > .35f && r < .55f, d); }
  printf("RESULT %s провалов %d\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
