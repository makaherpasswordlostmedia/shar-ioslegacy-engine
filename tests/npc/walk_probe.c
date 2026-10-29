// №510: персонаж миссии идёт по маршруту — высота над полом по пути и «дёрганье» (развороты за кадр). tests/npc/walk_probe.c LEVEL HOMER MSN name loc1 loc2 [loc3]
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
static const MsnLoc *loc(GameMsn *m, const char *nm) { for (uint32_t i = 0; i < m->f.nlocs; i++) { const char *s = msn_str(&m->f, m->f.locs[i].name); if (s && !strcmp(s, nm)) return &m->f.locs[i]; } return 0; }
int main(int argc, char **argv) {
  if (argc < 7 || bwData(argv[1], argv[2], argv[3])) return 2;
  bwNew(&W); GameMsn *m = &W.msn; unsigned nmis = m->f.nmissions; bwFree(&W);
  for (unsigned mi = 0; mi < nmis; mi++) {
    bwNew(&W); m = &W.msn; msn_start_mission(&m->rt, mi, 1); bwStep(&W, 0, 0.f, 0.f);
    GameNpc *n = 0; for (int k = 0; k < m->nnpc; k++) if (!strcmp(m->npc[k].name, argv[4])) n = &m->npc[k];
    if (!n) { bwFree(&W); continue; }
    n->nwp = 0; for (int a = 5; a < argc && n->nwp < GAME_NPC_WP; a++) { const MsnLoc *l = loc(m, argv[a]); if (!l) { printf("нет локатора %s\n", argv[a]); return 2; }
      n->wp[n->nwp].x = l->pos[0]; n->wp[n->nwp].y = l->pos[1]; n->wp[n->nwp].z = l->pos[2]; n->nwp++; }
    n->pos = n->wp[0]; n->iwp = 1; n->walking = 1; n->knock = 0; n->homing = 0;
    float maxOver = -9, minOver = 9, px = n->pos.x, pz = n->pos.z, hturn = 0, lastH = n->h; int flips = 0, moved = 0;
    for (int f = 0; f < 60 * 60 && n->walking; f++) {
      bwStep(&W, 0, 0.f, 0.f);
      float gy; if (colGround(bwCol(), n->pos.x, n->pos.z, n->pos.y + .6f, n->pos.y - 30.f, &gy, 0)) { float o = n->pos.y - gy; if (o > maxOver) maxOver = o; if (o < minOver) minOver = o; }
      float dh = fabsf(n->h - lastH); if (dh > 1.f && dh < 5.f) flips++; lastH = n->h; moved += hypotf(n->pos.x - px, n->pos.z - pz) > 1e-4f; px = n->pos.x; pz = n->pos.z; hturn += dh < 3.f ? dh : 0;
    }
    printf("mission %u %s: прошёл, над полом от %+.2f до %+.2f, кадров движения %d, резких разворотов %d, итог y=%.2f\n", mi, n->name, minOver, maxOver, moved, flips, n->pos.y);
    bwFree(&W); break;
  }
  return 0;
}
