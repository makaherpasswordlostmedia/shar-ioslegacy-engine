/* Метка этапа «купи костюм» (buyskin): ведёт к ближайшему гардеробу из skins.txt (вне комнаты — к двери его комнаты), а не стоит на метке прошлого этапа.
   Использование: skinmark_host level0N.msn interiors-lN.bin skins.txt [x y z — позиция игрока, по умолчанию 0 0 0]. Печатает MARK x y z на этапе buyskin или NOMARK.
   Красный контроль: -DMSN_BUYSKIN_MARK_OLD=1 (метки нет). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "mission/msn_game.h"
#include "rooms.h"
static Rooms rooms; static float spots[8][4]; static int nspots; static float ppos[3];
static int spotAt(int i, float *o) { if (i < 0 || i >= nspots) return 0; memcpy(o, spots[i], sizeof spots[i]); return 1; }
static int skinSpot(void *u, MsnVec3 *out) { (void)u; float t[3]; if (!roomsSpotTarget(&rooms, -1, spotAt, ppos[0], ppos[1], ppos[2], t)) return 0; out->x = t[0]; out->y = t[1]; out->z = t[2]; return 1; }
static MsnRuntime *RT; static int found; static float mk[3];
static void marker(void *u, const MsnMarker *m) { (void)u; if (m && RT->obj == MSN_OBJ_BUYSKIN && RT->status == MSN_RUNNING) { found = 1; mk[0] = m->pos.x; mk[1] = m->pos.y; mk[2] = m->pos.z; } }
static unsigned char *slurp(const char *p, size_t *n) { FILE *f = fopen(p, "rb"); if (!f) return 0; fseek(f, 0, SEEK_END); *n = (size_t)ftell(f); rewind(f); unsigned char *b = malloc(*n + 16); if (fread(b, 1, *n, f) != *n) return 0; fclose(f); return b; }
int main(int argc, char **argv) {
  if (argc < 4) return 2;
  size_t n; unsigned char *mb = slurp(argv[1], &n), *rb; if (!mb) return 2; MsnFile f; char err[200]; if (msn_open(&f, mb, n, err, sizeof err)) return 2;
  size_t rn; rb = slurp(argv[2], &rn); if (!rb || roomsParse(&rooms, rb, rn)) { printf("rooms failed\n"); return 2; }
  FILE *sf = fopen(argv[3], "r"); char ln[160]; while (sf && fgets(ln, sizeof ln, sf) && nspots < 8) { float a[4]; if (sscanf(ln, "spot %f %f %f %f", &a[0], &a[1], &a[2], &a[3]) == 4) memcpy(spots[nspots++], a, sizeof a); }
  if (argc >= 7) { ppos[0] = (float)atof(argv[4]); ppos[1] = (float)atof(argv[5]); ppos[2] = (float)atof(argv[6]); }
  int cases = 0, withMark = 0;
  for (unsigned mi = 0; mi < f.nmissions; mi++) {
    MsnRuntime rt; MsnGame mg; MsnGameApi api; memset(&api, 0, sizeof api); RT = &rt; found = 0;
    api.nav.marker = marker; api.shop.skin_spot = skinSpot;
    msn_game_init(&mg, &rt, &f, &api); msn_start_mission(&rt, mi, 0);
    for (int k = 0; k < 800 && rt.status != MSN_MISSION_DONE && !found; k++) { rt.status = rt.obj == MSN_OBJ_BUYSKIN ? rt.status : MSN_BETWEEN; rt.delay = 0; MsnWorld w; memset(&w, 0, sizeof w); w.player.x = ppos[0]; w.player.y = ppos[1]; w.player.z = ppos[2]; w.on_foot = 1; msn_tick(&rt, .01f, &w);
      if (rt.obj == MSN_OBJ_BUYSKIN && rt.status == MSN_RUNNING) { msn_tick(&rt, .01f, &w); break; } }
    if (rt.obj == MSN_OBJ_BUYSKIN) { cases++; if (found) { withMark++; printf("MARK %s %.1f %.1f %.1f\n", msn_str(&f, f.missions[mi].id), mk[0], mk[1], mk[2]); } else printf("NOMARK %s\n", msn_str(&f, f.missions[mi].id)); }
  }
  printf("buyskin missions %d, with marker %d\n", cases, withMark); return cases && withMark == cases ? 0 : 1;
}
