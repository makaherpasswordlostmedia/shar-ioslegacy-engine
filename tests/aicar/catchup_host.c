// Догонялка соперника гонки (SetStageAIRaceCatchupParams) по месту на пути гонки (разбор ночи 02.10 для приёмки L1, 03.10).
// m7 The Fat and Furious: трасса с возвратом (юг -> восток -> север -> финиш у старта). Прежняя мера «впереди ли соперник» —
// по прямой до ЛЮБОЙ точки его пути (mcRemainingFrom): игрок у старта считался почти на финише, и Смитерс весь заезд шёл с
// догонялкой ×1.5, даже далеко впереди (журнал бота: множитель 1.50 с 20-й секунды). Новая мера — пройденное по пути соперника
// (от места его старта через его точки): у соперника — по его ходу, у игрока — проекцией на этот путь, а из мест с возвратом —
// ближайшее к доле его гонки по его точкам (McEnv.pfrac, как место в гонке на экране).
// Ровная площадка, машина смитерса M7race.con, путь как у m7: (200,0) -> (200,200) -> (0,200) -> финиш (0,20), параметры m7
// 80 / 0.5 / 1.0 / 1.5. Случаи (множитель одного кадра mcUpdate):
//   ahead  — соперник за первой точкой (300 м из 780), игрок у старта, у финиша по прямой (доля 0.02): впереди -> < 1
//   behind — соперник на первом отрезке, игрок прошёл больше половины (0.6): соперник позади -> > 1
//   level  — соперник и игрок рядом на одном месте пути -> 0.9..1.1
//   first  — соперник на первом отрезке в 150 м от старта, игрок у старта (0.05): соперник впереди -> < 1 (первый отрезок не 0)
// Красный (tests/aicar/catchup.sh): -DMC_CATCHUP_GEO_OLD=1 — прежняя мера обязана упасть на ahead
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "msncar.h"
static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-6s %s  %s\n", n, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fx;
static ColWorld W;
static MsnCars M;
static float caseMult(float ax, float az, int wp, float px, float pz, float pfrac) {
  mcInit(&M);
  float s[3] = {0.f, 0.f, 0.f};
  McCar *c = mcSpawn(&M, &W, 0, "smith_v", s, 0.f, 1, "race", "Missions\\level01\\M7race.con", "smithers");
  if (!c) return -1.f;
  static const float P[4][3] = {{200.f, 0.f, 0.f}, {200.f, 0.f, 200.f}, {0.f, 0.f, 200.f}, {0.f, 0.f, 20.f}};
  for (int k = 0; k < 4; k++) mcWaypoint(&M, k, P[k], 1);
  const float rc[4] = {80.f, .5f, 1.f, 1.5f}; mcCatchup(&M, "smith_v", 0, rc, 4);
  carPlace(&c->car, &W, ax, .5f, az, 0.f); c->wp = wp;   // соперник на месте случая (точки до wp пройдены)
  Car pc; carInit(&pc, 0, &W, px, 0.f, pz, 0.f);
  McEnv e; memset(&e, 0, sizeof e); e.w = &W; e.player = &pc; e.driving = 1; e.ppos[0] = px; e.ppos[2] = pz; e.haveFrac = 1; e.pfrac = pfrac;
  mcUpdate(&M, &e, 1.f / 60.f, 0, 0);
  return c->mult;
}
int main(void) {
  memcpy(fx.h.magic, "COL1", 4); fx.h.ox = fx.h.oz = -400; fx.h.cell = 800; fx.h.W = fx.h.H = 1; fx.h.ntri = 2; fx.h.nref = 2;
  fx.t[0] = (ColTri){{-400, 0, -400}, {400, 0, 400}, {400, 0, -400}, {0, 1, 0}};
  fx.t[1] = (ColTri){{-400, 0, -400}, {-400, 0, 400}, {400, 0, 400}, {0, 1, 0}};
  fx.start[1] = 2; fx.refs[0] = 0; fx.refs[1] = 1;
  if (colInit(&W, &fx, sizeof fx)) { printf("FAIL: мир\n"); return 1; }
  char d[200]; float m;
  m = caseMult(200.f, 100.f, 1, 0.f, 10.f, .02f);
  snprintf(d, sizeof d, "соперник за 1-й точкой (200, 100), игрок у старта и у финиша по прямой, доля 0.02: множитель %.2f (нужно < 1)", m);
  check("ahead", m > 0.f && m < 1.f, d);
  m = caseMult(50.f, 0.f, 0, 0.f, 200.f, .6f);
  snprintf(d, sizeof d, "соперник на 1-м отрезке (50, 0), игрок прошёл 0.6: множитель %.2f (нужно > 1)", m);
  check("behind", m > 1.f, d);
  m = caseMult(200.f, 100.f, 1, 202.f, 98.f, 300.f / 780.f);
  snprintf(d, sizeof d, "рядом (оба у (200, 100), доля игрока 300/780): множитель %.2f (нужно 0.9..1.1)", m);
  check("level", m >= .9f && m <= 1.1f, d);
  m = caseMult(150.f, 0.f, 0, 0.f, 10.f, .05f);
  snprintf(d, sizeof d, "соперник на 1-м отрезке в 150 м от старта (доля 0.19), игрок 0.05: множитель %.2f (нужно < 1)", m);
  check("first", m > 0.f && m < 1.f, d);
  printf("RESULT %s провалов %d\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
