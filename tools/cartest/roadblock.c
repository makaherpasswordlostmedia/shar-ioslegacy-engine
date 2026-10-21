// Коллизия поперёк дорог трафика (вход пункта 11): машина на каждом отрезке roads-l1.bin через 2 м курсом вдоль него;
// кузов в коллизии глубже 0.3 м — дорогу из данных трафика что-то перекрывает (в оригинале по ней ездят машины).
// С 01.10 (группа corners-roads, решено терминалом по данным): «дорога трафика» — только отрезки дорог 0x3000003 с maxCars > 0
// и shortcut = 0 (build/sandbox/roads-l1.meta.tsv, tools/cartest/roads.py). Все 18 проб «в коллизии» ночи 30.09 (7 мест:
// дороги r1RoadNode7/8, r2RoadNode8, r3RoadNode8, r6RoadNode10) лежат на срезках ИИ (shortcut 1, maxCars 0: прыжок через щель
// у 124 220, двор с забором у 175 173, крыша-трамплин у −165 280, плита под мостом у 224 −470) — машин трафика там нет, это не
// ошибка коллизии. Срезки печатаются строками K (для гонок/погони), в счёт мест трафика не идут.
// Сборка -DRB_ALL_ROADS=1 — старое правило (все отрезки как трафик): отрицательный контроль гейта tests/roadblock.
//   V=viewer; cc -std=c11 -O1 -DSKIN_HOST -I $V -I tools/bots tools/cartest/roadblock.c tools/bots/world.c $V/game.c $V/car.c \
//      $V/col.c $V/props.c $V/stateprops.c $V/coins.c $V/homer.c $V/skin.c $V/rooms.c $V/roomcam.c $V/game_msn.c $V/mission/msn_*.c -lm -o build/roadblock
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"
#include "navgraph.h"
int main(void) {
  if (bwData("build/level.shr", "build/homer.shr", 0)) { fprintf(stderr, "roadblock: нет данных уровня\n"); return 2; }
  navLoad("build/sandbox/roads-l1.bin"); const ColWorld *w = bwCol();   // navLoad сам выходит, если нет roads-l1.bin
  static signed char traffic[4096]; int haveMeta = 0, ntr = 0;   // 1 — дорога трафика, 0 — срезка/без машин; по roads-l1.meta.tsv
  for (int i = 0; i < nroad && i < 4096; i++) traffic[i] = 1;
#ifndef RB_ALL_ROADS
  { FILE *m = fopen("build/sandbox/roads-l1.meta.tsv", "r"); char ln[512]; int i = 0;
    if (m) { while (fgets(ln, sizeof ln, m)) { if (ln[0] == '#') continue; char seg[128], rd[128]; int mc, sp, it, sc;
        if (sscanf(ln, "%127s %127s %d %d %d %d", seg, rd, &mc, &sp, &it, &sc) == 6 && i < 4096) { traffic[i] = mc > 0 && !sc; ntr += traffic[i]; i++; } }
      fclose(m); haveMeta = i == nroad; if (!haveMeta) fprintf(stderr, "roadblock: roads-l1.meta.tsv на %d отрезков, дорог %d — не тот файл, считаю все\n", i, nroad); }
    else fprintf(stderr, "roadblock: нет build/sandbox/roads-l1.meta.tsv (tools/cartest/roads.py) — считаю все отрезки дорогами трафика\n"); }
  if (!haveMeta) for (int i = 0; i < nroad && i < 4096; i++) traffic[i] = 1;
#endif
  int tot = 0, bad = 0, ktot = 0, kbad = 0;
  for (int i = 0; i < nroad; i++) { const Road *r = &roads[i]; float dx = r->bx - r->ax, dz = r->bz - r->az, L = hypotf(dx, dz); if (L < .5f) continue;
    for (float t = 0; t <= L; t += 2.f) { float x = r->ax + dx * t / L, y = r->ay + (r->by - r->ay) * t / L, z = r->az + dz * t / L;
      Car c; carInit(&c, NULL, w, x, y, z, atan2f(dx, dz)); if (fabsf(c.y - y) > 2.f) continue;   // поставилась на другую опору — не судим
      CarBox b; carBox(&c, &b); colProbeCar(w, &b); int tr = i >= 4096 || traffic[i]; if (tr) tot++; else ktot++;
      if (b.maxDepth > .3f) { int k = 0; for (int j = 1; j < b.n && j < COL_MAX_CONTACTS; j++) if (b.depth[j] > b.depth[k]) k = j;   // 6-я колонка: примитив COL1 (b12, c3, s7, t9)
        if (tr) bad++; else kbad++; printf("%c\t%d\t%.1f\t%.1f\t%.1f\t%.2f\t%c%u\n", tr ? 'R' : 'K', i, x, y, z, b.maxDepth, "tbcs"[b.type[k] & 3], (unsigned)b.index[k]); } } }
  fprintf(stderr, "проб на дорогах трафика %d, машина в коллизии %d; на срезках ИИ (без трафика) %d, в коллизии %d%s\n", tot, bad, ktot, kbad,
          haveMeta ? "" : " (без разметки — всё считается трафиком)");
  printf("S\t%d\t%d\n", tot, bad);   // итог для станка: всего проб, в коллизии (только дороги трафика)
  printf("Q\t%d\t%d\n", ktot, kbad); // срезки ИИ (строки K — их пробы в коллизии): проб, в коллизии (справочно)
  (void)ntr;
  return tot > 0 ? 0 : 3;               // ни одной пробы — данные не те, это не «чистые дороги»
}
