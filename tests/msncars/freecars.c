// №418 (Роб 09.10: «на уровнях нет уникальных машин, которые стоят только в одном месте; L5 J4-7 — Bigfoot»): машина мира
// каждого уровня (viewer/worldcars.h — CarStart-локатор с именем машины в данных, по одному на уровень) стоит в своей точке,
// у неё есть модель в пакете msncars-l<N>.shr уровня и в неё можно сесть (△ рядом: main.c mvWorldCarNear + mvTakeWorldCar).
// Мир ботов (tools/bots/world.c) — тот же viewer/game_msn.c, msncar.c, что EBOOT; список машин — тот же worldcars.h, что main.c.
//   tests/msncars/freecars.sh [--gate]   (--gate: сборка с -DWORLD_CARS_OLD — только ракетная L1 — обязана упасть)
//   host HOMER.shr LEVEL.shr MSN [LEVEL.shr MSN ...]   (msncars-l<N>.shr — рядом с LEVEL.shr)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "msncar.h"
#include "placecode.h"
#include "worldcars.h"

static int fails;
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4 || (argc - 2) % 2) { fprintf(stderr, "freecars HOMER.shr LEVEL.shr MSN [...]\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  for (int a = 2; a + 1 < argc; a += 2) {
    if (bwData(argv[a], argv[1], argv[a + 1])) { printf("FAIL: данные %s\n", argv[a]); return 1; }
    bwNew(&W); int lv = bwLevel(), carGeo = 0, au = 0; bwMissionPacks(&carGeo, &au);
    gameMsnWorldCarsReset();   // как levelUnload: список машин мира — заново на каждом уровне
    // как main.c worldCarsPlace (NEW GAME)
    for (unsigned i = 0; i < sizeof WORLD_CAR_LIST / sizeof WORLD_CAR_LIST[0]; i++)
      if (WORLD_CAR_LIST[i].level == lv && W.haveMsn) gameMsnWorldCar(&W.msn, WORLD_CAR_LIST[i].name, WORLD_CAR_LIST[i].p, mcCarHeading(WORLD_CAR_LIST[i].h));
    for (int i = 0; i < 120; i++) { bwStep(&W, 0, 0, 0);
      if (getenv("FC_DEBUG") && i % 10 == 0 && W.haveMsn) for (unsigned k = 0; k < sizeof WORLD_CAR_LIST / sizeof WORLD_CAR_LIST[0]; k++) if (WORLD_CAR_LIST[k].level == lv) {
        const McCar *c = mcFind(&W.msn.cars, WORLD_CAR_LIST[k].name); if (c) printf("  f%d %s %.2f %.2f %.2f h %.2f v %.2f\n", i, WORLD_CAR_LIST[k].name, c->car.x, c->car.y, c->car.z, c->car.h, c->car.v); } }
    // ожидание — из данных: машина уровня с именем в CarStart (таблица ниже снята tools/missions/p3dlocs, z отзеркален)
    static const struct { int lv; const char *name; float p[3]; } WANT[] = {
      {1, "rocke_v", {-90.2f, -0.77f, 211.6f}}, {2, "mono_v", {-215.7f, 42.7f, -488.0f}}, {3, "knigh_v", {-489.7f, -49.1f, -94.8f}},
      {4, "atv_v", {410.1f, -2.3f, -481.1f}}, {5, "oblit_v", {113.2f, 14.7f, -311.9f}}, {6, "hype_v", {-493.0f, -59.3f, 69.5f}},
      {7, "dune_v", {199.6f, 9.3f, 363.7f}}};
    for (unsigned w = 0; w < sizeof WANT / sizeof WANT[0]; w++) {
      if (WANT[w].lv != lv) continue;
      char pc[16]; placeCode(WANT[w].p[0], WANT[w].p[2], pc, sizeof pc);
      const McCar *c = W.haveMsn ? mcFind(&W.msn.cars, WANT[w].name) : 0;
      int model = mcGeoFind(WANT[w].name) != 0;
      float d = c ? hypotf(c->car.x - WANT[w].p[0], c->car.z - WANT[w].p[2]) : -1.f, dy = c ? c->car.y - WANT[w].p[1] : 0.f;
      // стоит: в 1.5 м от точки данных по XZ (правило гейта: выталкивание из соседней коллизии при посадке — L2 mono_v 1.09 м) и на
      // опоре под локатором (первая земля ниже точки локатора + 0.5 м; L3 knigh_v: локатор на 2.18 м выше земли)
      float gy = WANT[w].p[1]; { float g_; if (colGround(bwCol(), WANT[w].p[0], WANT[w].p[2], WANT[w].p[1] + .5f, WANT[w].p[1] - 20.f, &g_, 0)) gy = g_; }
      float dg = c ? c->car.y - gy : 99.f;
      int stand = c && c->on && d >= 0.f && d < 1.5f && fabsf(dg) < .3f;
      // сесть: Гомер пешком в 2 м от машины — mvWorldCarNear (JACK_R main.c) -> mvTakeWorldCar
      int near = -1, took = 0; float wc[4];
      if (stand) { near = gameMsnWorldCarNear(&W.msn, c->car.x + 2.f, c->car.z, 2.5f, wc);
                   if (near >= 0) took = gameMsnTakeWorld(&W.msn, near) && !strcasecmp(gameMsnForcedCar(&W.msn) ? gameMsnForcedCar(&W.msn) : "", WANT[w].name); }
      int ok = stand && model && near >= 0 && took;
      printf("CHECK L%d %-8s %s  %s: стоит %d (от точки данных %.2f м, над опорой %.2f, локатор %.2f), модель в пакете %d, рядом найдена %d, сел — машина игрока %s\n",
             lv, WANT[w].name, ok ? "OK  " : "FAIL", pc, stand, d, dg, dy, model, near >= 0, took ? WANT[w].name : "-");
      fails += !ok;
    }
  }
  printf("RESULT %s %d\n", fails ? "FAIL" : "OK", fails);
  return fails ? 1 : 0;
}
