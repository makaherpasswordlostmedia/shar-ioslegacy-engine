// №510: персонаж миссии обходит стоящего на пути игрока (Милхаус и Барт): доходит до точки, не заходит в капсулу, не дёргает курс.
//   tests/npc/avoid.c LEVEL HOMER MSN name loc1 loc2 ; без флага — обходит; -DGAME_NPC_AVOID_OLD=1 — красный контроль (стоит в упор)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
static const MsnLoc *loc(GameMsn *m, const char *nm) { for (uint32_t i = 0; i < m->f.nlocs; i++) { const char *s = msn_str(&m->f, m->f.locs[i].name); if (s && !strcmp(s, nm)) return &m->f.locs[i]; } return 0; }
int main(int argc, char **argv) {
  if (argc < 7 || bwData(argv[1], argv[2], argv[3])) return 2;
  bwNew(&W); unsigned nmis = W.msn.f.nmissions; bwFree(&W);
  for (unsigned mi = 0; mi < nmis; mi++) {
    bwNew(&W); GameMsn *m = &W.msn; msn_start_mission(&m->rt, mi, 1); bwStep(&W, 0, 0.f, 0.f);
    GameNpc *n = 0; for (int k = 0; k < m->nnpc; k++) if (!strcmp(m->npc[k].name, argv[4])) n = &m->npc[k];
    if (!n) { bwFree(&W); continue; }
    const MsnLoc *a = loc(m, argv[5]), *b = loc(m, argv[6]); if (!a || !b) return 2;
    n->nwp = 2; n->wp[0].x = a->pos[0]; n->wp[0].y = a->pos[1]; n->wp[0].z = a->pos[2]; n->wp[1].x = b->pos[0]; n->wp[1].y = b->pos[1]; n->wp[1].z = b->pos[2];
    n->pos = n->wp[0]; n->iwp = 1; n->walking = 1; n->knock = 0; n->homing = 0;
    // игрок пешком стоит на середине отрезка
    float mx = (a->pos[0] + b->pos[0]) * .5f, mz = (a->pos[2] + b->pos[2]) * .5f; float gy = a->pos[1];
    homerPlace(&W.homer, bwCol(), mx, gy + .2f, mz, 0.f);
    float minD = 9.f, lastH = n->h; int flips = 0, reached = 0, stuckFrames = 0, standWalking = 0; float px = n->pos.x, pz = n->pos.z;
    for (int f = 0; f < 60 * 40; f++) {
      homerPlace(&W.homer, bwCol(), mx, W.homer.y, mz, 0.f);   // игрок неподвижен
      bwStep(&W, 0, 0.f, 0.f);
      float d = hypotf(n->pos.x - W.homer.x, n->pos.z - W.homer.z); if (d < minD) minD = d;
      float dh = fabsf(n->h - lastH); if (dh > .5f && dh < 5.7f) flips++; lastH = n->h;
      int moved = hypotf(n->pos.x - px, n->pos.z - pz) > 1e-4f; px = n->pos.x; pz = n->pos.z;
      if (!moved && n->walking) { stuckFrames++; if (!n->blocked) standWalking++; }
      if (!n->walking && n->iwp >= n->nwp) { reached = 1; break; }
    }
    printf("mission %u %s: дошёл=%d, ближе всего к игроку %.2f м (граница %.2f), стоял на месте %d кадров из них с походкой %d, резких разворотов %d\n", mi, n->name, reached, minD, GAME_NPC_RADIUS + HOMER_RADIUS, stuckFrames, standWalking, flips);
    int bad = !reached || minD < GAME_NPC_RADIUS + HOMER_RADIUS - .05f || flips > 2;
    printf("%s\n", bad ? "FAIL" : "PASS"); bwFree(&W); return bad;
  }
  printf("нет персонажа\n"); return 2;
}
