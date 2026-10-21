/* Ночь 11.10: AddStageCharacter с пустым локатором персонажа (L4 m2, L6 m5) ставил игрока в (0,0,0). Для каждой миссии пакета MSN1 — вызовы player.reset по этапам: сколько с at != NULL
   в начале мира. Использование: stagechar_host level0N.msn; красный контроль: -DMSN_STAGECHAR_OLD=1 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "mission/msn_game.h"
static int bad, calls; static const char *curId;
static void reset(void *u, const MsnPlace *at, const MsnPlace *car, const char *name) {
  (void)u; (void)car; (void)name; calls++;
  if (at && fabsf(at->pos.x) < 1e-3f && fabsf(at->pos.z) < 1e-3f) { bad++; printf("ORIGIN %s\n", curId); }
}
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *fd = fopen(argv[1], "rb"); if (!fd) return 2; fseek(fd, 0, SEEK_END); long size = ftell(fd); rewind(fd);
  void *data = malloc(size); if (fread(data, 1, size, fd) != (size_t)size) return 2; fclose(fd); MsnFile f; char err[200];
  if (msn_open(&f, data, size, err, sizeof err)) { fprintf(stderr, "FAIL %s\n", err); return 2; }
  for (unsigned mi = 0; mi < f.nmissions; mi++) {
    MsnRuntime rt; MsnGame mg; MsnGameApi api; memset(&api, 0, sizeof api); api.player.reset = reset; curId = msn_str(&f, f.missions[mi].id);
    msn_game_init(&mg, &rt, &f, &api); msn_start_mission(&rt, mi, 0);
    for (int n = 0; n < 600 && rt.status != MSN_MISSION_DONE; n++) { rt.status = MSN_BETWEEN; rt.delay = 0; MsnWorld w; memset(&w, 0, sizeof w); msn_tick(&rt, .01f, &w); }
  }
  printf("calls %d, ставит игрока в начало мира: %d\n", calls, bad); free(data); return bad ? 1 : 0;
}
