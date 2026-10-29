// №510: высота персонажей миссий над полом (Милхаус L2 «ходит как на этаж выше»). Запуск миссии, Гомер пешком на месте, 40 с шагов;
// печатает персонажей: поза, пол прямо под ногами, сколько опор над XZ, и самое большое превышение над ближайшей опорой снизу.
//   tests/npc/height_probe.c LEVEL HOMER MSN [mission]
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) return 2;
  int only = argc > 4 ? atoi(argv[4]) : -1; int bad = 0;
  bwNew(&W); unsigned n = W.msn.f.nmissions; bwFree(&W);
  for (unsigned i = 0; i < n; i++) {
    if (only >= 0 && (int)i != only) continue;
    bwNew(&W); GameMsn *m = &W.msn; msn_start_mission(&m->rt, i, 1);
    float worst[GAME_NPC_MAX]; for (int k = 0; k < GAME_NPC_MAX; k++) worst[k] = 0.f; float wy[GAME_NPC_MAX], wf[GAME_NPC_MAX], wx[GAME_NPC_MAX], wz[GAME_NPC_MAX];
    for (int f = 0; f < 60 * 40; f++) {
      bwStep(&W, 0, 0.f, 0.f);
      if (f % 30) continue;
      for (int k = 0; k < m->nnpc; k++) { const GameNpc *p = &m->npc[k]; if (p->interior[0] || p->knock) continue;
        float gy; if (!colGround(bwCol(), p->pos.x, p->pos.z, p->pos.y + .6f, p->pos.y - 30.f, &gy, 0)) continue;
        float over = p->pos.y - gy;
        if (fabsf(over) > fabsf(worst[k])) { worst[k] = over; wy[k] = p->pos.y; wf[k] = gy; wx[k] = p->pos.x; wz[k] = p->pos.z; } } }
    for (int k = 0; k < m->nnpc; k++) if (fabsf(worst[k]) > .3f) { printf("mission %u: %s y=%.2f floor-under=%.2f (%+.2f) at %.1f,%.1f\n", i, m->npc[k].name, wy[k], wf[k], worst[k], wx[k], wz[k]); bad++; }
    bwFree(&W);
  }
  printf("RESULT npc-height off-floor missions=%d\n", bad); return 0;
}
