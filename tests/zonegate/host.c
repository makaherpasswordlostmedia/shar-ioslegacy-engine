// Сверка близнеца (правка 181): путь бота оригинала (build/twins/o4/<прогон>/drive.tsv, оси оригинала) через ворота порта —
// тот же код viewer/zonegate.h, что в EBOOT. Печать: START маска; EV кадр ворота маска_до маска_после
//   cc -std=c99 -O2 -I viewer tests/zonegate/host.c -lm -o build/zonegate_host && build/zonegate_host GAT1.bin drive.tsv
#include <stdio.h>
#include <stdlib.h>
#include "zonegate.h"
int main(int argc, char **argv) {
  if (argc < 3) { puts("BAD аргументы"); return 2; }
  FILE *f = fopen(argv[1], "rb"); if (!f) { puts("BAD нет GAT1"); return 2; }
  unsigned char h[16]; if (fread(h, 1, 16, f) != 16 || memcmp(h, "GAT1", 4)) { puts("BAD не GAT1"); return 2; }
  unsigned ng, np; memcpy(&ng, h + 4, 4); memcpy(&np, h + 8, 4);
  if (ng > ZG_MAX || np > ZG_PLACES) { puts("BAD много ворот"); return 2; }
  static ZoneGate g[ZG_MAX]; static ZonePlace p[ZG_PLACES];
  if (fread(g, sizeof(ZoneGate), ng, f) != ng || fread(p, sizeof(ZonePlace), np, f) != np) { puts("BAD чтение"); return 2; }
  fclose(f);
#ifdef ZG_PLANT_SHIFT   // отрицательный контроль: ворота сдвинуты на 40 м по x — загрузки не у тех мест и не в те кадры
  for (unsigned i = 0; i < ng; i++) g[i].c[0] += 40.f;
#endif
  FILE *t = fopen(argv[2], "r"); if (!t) { puts("BAD нет пути"); return 2; }
  char ln[512]; if (!fgets(ln, sizeof ln, t)) return 2;
  static unsigned char was[ZG_MAX]; unsigned res = 0; int started = 0;
  while (fgets(ln, sizeof ln, t)) {
    int fr; float x, y, zo; if (sscanf(ln, "%d\t%f\t%f\t%f", &fr, &x, &y, &zo) != 4) continue;
    float z = -zo;   // ось порта
    if (!started) { res = zonePlaceNear(p, (int)np, x, z, 0xFFFFu); printf("START %d %04x\n", fr, res); started = 1;
                    for (unsigned i = 0; i < ng; i++) was[i] = (unsigned char)zoneGateIn(&g[i], x, y, z, 1.5f); continue; }
    int fired = -1; unsigned before = res;
    res = zoneGatesStep(g, (int)ng, was, res, x, y, z, 1.5f, &fired);
    if (res != before) printf("EV %d %d %04x %04x\n", fr, fired, before, res);
  }
  return 0;
}
