// Правка Роба 219 (03.10: «Лиза в школе ходит в потолке, миссию не сдать»). Данные диска (art/missions/level01/m1.p3d): место
// m1_lisa_place y −20 (пол школы), точки маршрута lisa_walk_1/2 — y −16,5 (на 3,5 м выше), маршрут m1i.mfk: walk_1, walk_2, walk_1.
// Игра без экрана (tools/bots/world.c): Лиза как AddNPC — в школе, по тем же точкам; 30 с шага мира — высота не уходит от пола
// больше чем на 0,3 м, дошла до конца маршрута. Красный (tests/npc/lisa.sh): -DGAME_NPC_WP_Y=1 — прежняя высота к точке маршрута
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "lisa_host LEVEL.shr HOMER.shr level01.msn\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  bwNew(&W); for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
  GameMsn *M = &W.msn; if (M->nnpc >= GAME_NPC_MAX) { printf("FAIL: нет места для персонажа\n"); return 1; }
  GameNpc *n = &M->npc[M->nnpc++]; memset(n, 0, sizeof *n);
  strcpy(n->name, "lisa"); strcpy(n->interior, "SpringfieldElementary"); n->kind = MSN_NPC_MISSION;
  n->pos = (MsnVec3){500.25f, -20.f, 360.34f};
  const MsnVec3 w1 = {499.47f, -16.5f, 354.36f}, w2 = {499.34f, -16.5f, 349.69f};
  n->wp[0] = w1; n->wp[1] = w2; n->wp[2] = w1; n->nwp = 3; n->walking = 1;
  float ymax = -1e9f, ymin = 1e9f;
  for (int f = 0; f < 60 * 30 && n->walking; f++) { bwStep(&W, 0, 0, 0); if (n->pos.y > ymax) ymax = n->pos.y; if (n->pos.y < ymin) ymin = n->pos.y; }
  int ok = ymax <= -20.f + 0.3f && ymin >= -20.f - 0.3f && !n->walking;
  printf("Лиза: высота %.2f..%.2f (пол −20), маршрут %s, у конца (%.2f, %.2f, %.2f)\n", ymin, ymax, n->walking ? "НЕ ПРОЙДЕН" : "пройден", n->pos.x, n->pos.y, n->pos.z);
  printf("RESULT %s\n", ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}
