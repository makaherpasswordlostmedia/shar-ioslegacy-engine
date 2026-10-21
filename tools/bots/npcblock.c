// Твёрдые персонажи (пункт 8, отзыв Роба 28.09: «Мардж проходит сквозь Гомера»): игра без экрана, m0 как NEW GAME.
// Мардж останавливается на своём месте (маршрут снят — чтобы шла проверка Гомера, а не её ходьбы), Гомер ставится в 3 м
// от неё с четырёх сторон и 3 с идёт стиком прямо на неё. Итог по каждой попытке: минимум расстояния между центрами и
// прошёл ли насквозь (оказался по ту сторону). Потом Мардж идёт по своему маршруту на стоящего Гомера: не сквозь него.
//   npcblock LEVEL HOMER MSN   -> строки "B ..." и итог "RESULT OK|FAIL" (tests/missions/npc_block.sh)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "npcblock: нет данных\n"); return 2; }
  bwNew(&W);
  if (!W.haveMsn || !W.haveHomer) { fprintf(stderr, "npcblock: нет миссий/Гомера\n"); return 2; }
  GameNpc *mg = (GameNpc *)gameMsnNpc(&W.msn, "marge");
  if (!mg) { fprintf(stderr, "npcblock: Мардж не поставлена сценарием m0\n"); return 2; }
  mg->walking = 0; mg->nwp = 0;
  const float need = GAME_NPC_RADIUS + HOMER_RADIUS - .02f;   // допуск на шаг выталкивания
  int bad = 0;
  for (int k = 0; k < 4; k++) {                               // Гомер подходит с четырёх сторон
    float a = k * 1.5707963f, sx = mg->pos.x + sinf(a) * 3.f, sz = mg->pos.z + cosf(a) * 3.f;
    homerPlace(&W.homer, bwCol(), sx, mg->pos.y + .5f, sz, a + 3.14159265f);
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);          // встал на землю
    float dmin = 1e9f, side0 = (W.homer.x - mg->pos.x) * sinf(a) + (W.homer.z - mg->pos.z) * cosf(a), side1 = side0;
    for (int f = 0; f < 180; f++) {
      float r = atan2f(mg->pos.x - W.homer.x, mg->pos.z - W.homer.z) - W.homer.camYaw;
      bwStep(&W, 0, -sinf(r), -cosf(r));                       // стик на Мардж (как миссионер: вправо камеры = −x)
      float d = hypotf(W.homer.x - mg->pos.x, W.homer.z - mg->pos.z); if (d < dmin) dmin = d;
      side1 = (W.homer.x - mg->pos.x) * sinf(a) + (W.homer.z - mg->pos.z) * cosf(a);
    }
    int through = side0 > 0.f && side1 < 0.f, fail = dmin < need || through;
    printf("B подход %d: минимум %.3f м (нужно >= %.2f), %s -> %s\n", k, dmin, need, through ? "НАСКВОЗЬ" : "не прошёл сквозь", fail ? "FAIL" : "ok");
    bad += fail;
  }
  {   // Мардж идёт по маршруту прямо через место, где стоит Гомер
    homerPlace(&W.homer, bwCol(), mg->pos.x + 2.f, mg->pos.y + .5f, mg->pos.z, 0.f);
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    mg->wp[0].x = mg->pos.x + 4.f; mg->wp[0].y = mg->pos.y; mg->wp[0].z = mg->pos.z; mg->nwp = 1; mg->iwp = 0; mg->walking = 1;
    float dmin = 1e9f;
    for (int f = 0; f < 60 * 8; f++) { bwStep(&W, 0, 0, 0); float d = hypotf(W.homer.x - mg->pos.x, W.homer.z - mg->pos.z); if (d < dmin) dmin = d; }
    int fail = dmin < need;
    printf("B Мардж идёт на Гомера: минимум %.3f м -> %s\n", dmin, fail ? "FAIL" : "ok");
    bad += fail;
  }
  printf("RESULT %s\n", bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
