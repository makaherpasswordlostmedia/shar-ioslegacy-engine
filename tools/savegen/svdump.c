// Печать записи DATA.BIN через настоящий savegame.c (только чтение).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "savegame.h"
int main(int argc, char **argv) {
  for (int a = 1; a < argc; a++) {
    FILE *f = fopen(argv[a], "rb"); if (!f) { perror(argv[a]); continue; } uint8_t b[SV_BYTES + 16]; unsigned n = (unsigned)fread(b, 1, sizeof b, f); fclose(f);
    SaveGame s; int r = svRead(b, n, &s); printf("%s: %u байт, svRead=%d (0 ок)\n", argv[a], n, r); if (r) continue;
    char t[1200]; svProgressText(&s, t, sizeof t);
    printf("  seq=%u дата %04u-%02u-%02u %02u:%02u level=%u msnLevel=%u msnCompleted=%08x coins=%d skin=%u\n  %s\n", s.seq, s.year, s.month, s.day, s.hour, s.minute, s.level, s.msnLevel, s.msnCompleted, s.coins, s.skin, t);
    printf("  cards:"); for (int L = 1; L < SV_LEVELS; L++) printf(" L%d=%02x", L, s.cards[L]); printf("\n  wasps:"); for (int L = 1; L < SV_LEVELS; L++) printf(" L%d=%x", L, s.wasps[L]);
    printf("\n  gags:"); for (int L = 1; L < SV_LEVELS; L++) printf(" L%d=%llx", L, (unsigned long long)s.gags[L]); printf("\n  owned:"); for (int L = 1; L < SV_LEVELS; L++) printf(" L%d=%x", L, s.owned[L]);
    printf("\n  svLvReached=%d; по уровням (маска миссий / строки):", svLvReached(&s)); for (int L = 1; L <= 7; L++) { uint32_t m = 0; unsigned r2 = 0; int g = svLvGet(&s, L, &m, &r2); printf(" L%d[%d %08x %02x]", L, g, m, r2); }
    printf("\n  ext:"); for (int i = 0; i < 48; i++) printf("%02x", s.ext[i]); printf("\n");
  }
  return 0;
}
