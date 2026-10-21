// №510: поправка высоты стоп клипов общего набора npd_loco_* (viewer/skin.c skinFootLift). Модели: tests/npc/footlift.c chars/*.chr
//   Ожидание: свой набор (Барт, Лиза, Гомер) — 0; общий набор у ребёнка (Милхаус, Ральф, Нельсон) — отрицательная поправка (опустить), у Скиннера/Гила — положительная.
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "skin.h"
int main(int argc, char **argv) {
  int bad = 0;
  for (int a = 1; a < argc; a++) {
    SkinModel *m = skinLoad(argv[a]); if (!m) { printf("нет %s\n", argv[a]); bad++; continue; }
    const char *b = strrchr(argv[a], '/'); b = b ? b + 1 : argv[a];
    for (int c = 0; c < skinClipCount(m); c++) { const char *n = skinClipName(m, c); if (!strstr(n, "loco_walk") && !strstr(n, "loco_idle_rest")) continue;
      float l = skinFootLift(m, c); printf("%-14s %-22s lift %+.3f\n", b, n, l);
      int own = strstr(n, "brt_") || strstr(n, "lsa_") || strstr(n, "hom_") || strstr(n, "mrg_") || strstr(n, "apu_");
      if (own && fabsf(l) > .12f) { printf("FAIL: собственный набор сдвинут сильно\n"); bad++; }
      if (!strcmp(b, "milhouse.chr") && l > -.1f) { printf("FAIL: Милхаус не опущен\n"); bad++; } }
    skinFree(m);
  }
  printf("%s\n", bad ? "FAIL" : "PASS"); return bad;
}
