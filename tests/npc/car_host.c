// Правка Роба 217 (03.10: «Мардж не замечает машину — проходит сквозь неё и только потом начинает обходить»). Игра без экрана
// (tools/bots/world.c): машина игрока на спавне, персонаж миссии в 5 м по одну сторону кузова, точка маршрута — в 5 м по другую.
// Персонаж не входит в кузов (с половиной своего радиуса) и доходит до точки; три поворота машины. Красный (tests/npc/car.sh):
// -DGAME_NPC_CAR_AVOID=0 — прежнее: идёт сквозь кузов
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
#include "world.h"
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "car_host LEVEL.shr HOMER.shr level01.msn\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  int bad = 0;
  const float hs[3] = {1.5708f, 0.4f, 2.6f};
  for (int k = 0; k < 3; k++) {
    bwNew(&W); for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    carPlace(&W.car, bwCol(), W.car.x, W.car.y + .3f, W.car.z, hs[k]); carSetSpeed(&W.car, 0.f);
    for (int f = 0; f < 20; f++) bwStep(&W, 0, 0, 0);
    const Car *c = &W.car; float fx = sinf(c->h), fz = cosf(c->h), rx = fz, rz = -fx;
    float cx = c->x + fx * c->p.bodyOfs, cz = c->z + fz * c->p.bodyOfs;
    GameMsn *M = &W.msn; if (M->nnpc >= GAME_NPC_MAX) { printf("FAIL: нет места для персонажа\n"); return 1; }
    GameNpc *n = &M->npc[M->nnpc++]; memset(n, 0, sizeof *n);
    strcpy(n->name, "marge"); n->kind = MSN_NPC_MISSION;
    n->pos = (MsnVec3){cx - rx * 5.f, c->y, cz - rz * 5.f};
    n->wp[0] = (MsnVec3){cx + rx * 5.f, c->y, cz + rz * 5.f}; n->nwp = 1; n->walking = 1;
    float worst = 1e9f;
    for (int f = 0; f < 60 * 20 && n->walking; f++) {
      bwStep(&W, 0, 0, 0);
      float ax = (n->pos.x - cx) * rx + (n->pos.z - cz) * rz, az = (n->pos.x - cx) * fx + (n->pos.z - cz) * fz;
      float ex = fabsf(ax) - (c->p.halfW + GAME_NPC_RADIUS * .5f), ez = fabsf(az) - (c->p.halfL + GAME_NPC_RADIUS * .5f);
      float out = ex > ez ? ex : ez;   // > 0 — снаружи кузова
      if (out < worst) worst = out;
      if (getenv("CAR_DBG") && f % 30 == 0) printf("  f%d local %.2f %.2f walking %d iwp %d\n", f, ax, az, n->walking, n->iwp);
    }
    int ok = worst > 0.f && !n->walking;
    printf("курс %.2f: ближе всего к кузову %.2f м (меньше 0 — внутри), маршрут %s\n", hs[k], worst, n->walking ? "НЕ ПРОЙДЕН" : "пройден");
    if (!ok) bad++;
    M->nnpc--;
  }
  printf("RESULT %s\n", bad ? "FAIL" : "PASS");
  return bad ? 1 : 0;
}
