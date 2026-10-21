// Разбор блока света LGT1 движком (viewer/levlight.h) на Маке: тот же код, что в EBOOT (main.c levelLightApply).
//   parse_host level.shr [plant]   -> строка LIGHTHOST (как строка LIGHT смоука) и код 0; битый блок — код 1
//   plant: sum — испортить байт блока (сумма не сходится), ver — версия блока 2, cut — секция обрезана до блока
// Сверка с диском — tests/light/light_check.py; этот тест проверяет, что движок читает то, что пишет экспорт.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../viewer/levlight.h"
#include "../../viewer/skin.h"

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "parse_host level.shr [sum|ver|cut]\n"); return 2; }
  FILE *f = fopen(argv[1], "rb"); if (!f) { perror(argv[1]); return 2; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104) return 2;
  unsigned carOff, pvsOff; memcpy(&carOff, hdr + 100, 4); memcpy(&pvsOff, hdr + 88, 4);
  static unsigned char cb[4096]; unsigned sz = sizeof cb;               // как main.c: секция < 4 КБ, до PVS1
  if (pvsOff > carOff && pvsOff - carOff < sz) sz = pvsOff - carOff;
  fseek(f, carOff, SEEK_SET); unsigned n = (unsigned)fread(cb, 1, sz, f); fclose(f);
  if (argc > 2) {
    unsigned u[7]; memcpy(u, cb + 4, sizeof u); unsigned o = u[5] + u[6];
    if (!strcmp(argv[2], "sum")) cb[o + 40] ^= 0x10;
    else if (!strcmp(argv[2], "ver")) { unsigned v = 2; memcpy(cb + o + 4, &v, 4); }
    else if (!strcmp(argv[2], "cut")) n = o + 64;
  }
  LevLight L; int r = levLightParse(cb, n, &L);
  unsigned sun = SKIN_SUN_ABGR, amb = SKIN_AMB_ABGR;
  if (r == 1) { sun = levLightScale(SKIN_SUN_ABGR, L.dirS); amb = levLightScale(SKIN_AMB_ABGR, L.ambS); }
  printf("LIGHTHOST level=%u src=%s r=%d group=%s ndir=%u amb=%06x ambS=%.3f,%.3f,%.3f dirS=%.3f,%.3f,%.3f skinSun=%08x skinAmb=%08x\n",
         L.level, levLightError(r), r, r == 1 ? L.group : "-", L.ndir, L.amb & 0xffffff, L.ambS[0], L.ambS[1], L.ambS[2],
         L.dirS[0], L.dirS[1], L.dirS[2], sun, amb);
  return r == 1 ? 0 : 1;
}
