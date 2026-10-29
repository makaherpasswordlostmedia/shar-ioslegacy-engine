// Собирает запись «пройдено всё» настоящими модулями игры (savegame.c, collect.c, mission/msn_file.c) -> allsave.bin (SV_BYTES).
//   mkallsave SET MISSIONS_DIR OUT.bin   SET — папка набора (collect-l1.shr, lN/collect-lN.shr); MISSIONS_DIR — levelNN.msn
// Содержимое: миссии всех уровней (сюжет, бонус-миссия, уличные гонки), карточки/осы/гэги всех уровней, купленное всех уровней, уровень записи 7.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "savegame.h"
#include "collect.h"
#include "mission/msn.h"
static void *slurp(const char *p, size_t *n) {
  FILE *f = fopen(p, "rb"); if (!f) return NULL; fseek(f, 0, SEEK_END); long z = ftell(f); fseek(f, 0, SEEK_SET);
  void *b = aligned_alloc(16, ((size_t)z + 15) & ~15u); if (fread(b, 1, (size_t)z, f) != (size_t)z) { fclose(f); free(b); return NULL; } fclose(f); *n = (size_t)z; return b;
}
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: mkallsave SET MISSIONS_DIR OUT.bin\n"); return 2; }
  SaveGame g; svClear(&g); g.coins = 9999;
  for (int L = 1; L <= 7; L++) {
    char p[400]; size_t n; MsnFile mf; char err[160] = {0};
    snprintf(p, sizeof p, "%s/level%02d.msn", argv[2], L); void *mb = slurp(p, &n);
    if (!mb || msn_open(&mf, mb, n, err, sizeof err)) { fprintf(stderr, "L%d: %s: %s\n", L, p, err); return 1; }
    uint32_t all = 0, story = 0; int ns = 0, st[32]; unsigned rows = 0x80;
    printf("L%d: миссий %u\n", L, mf.nmissions);
    for (unsigned i = 0; i < mf.nmissions; i++) {
      unsigned fl = mf.missions[i].flags; int skip = (fl & (MSN_MF_NOSCRIPT | MSN_MF_TRANSITION)) != 0;
      printf("   m%-2u flags=%03x%s%s%s%s%s%s%s\n", i, fl, fl & MSN_MF_BONUS ? " BONUS" : "", fl & MSN_MF_STREETRACE ? " RACE" : "", fl & MSN_MF_GAMBLE ? " GAMBLE" : "", fl & MSN_MF_BONUSMISSION ? " BONUSMSN" : "", fl & MSN_MF_NOSCRIPT ? " NOSCRIPT" : "", fl & MSN_MF_TRANSITION ? " TRANSITION" : "", fl & MSN_MF_GAMEOVER ? " GAMEOVER" : "");
      if (!skip) all |= 1u << i;
      if (!(fl & (MSN_MF_BONUS | MSN_MF_NOSCRIPT | MSN_MF_TRANSITION)) && ns < 32) st[ns++] = (int)i;
    }
    for (int k = 0; k < 7; k++) { int i = ns - 7 + k; if (i >= 0) rows |= 1u << k; }
    story = 0; for (int k = 0; k < ns; k++) story |= 1u << st[k];
    printf("   маска всех %08x, сюжетных %08x (%d), строки MISSION SELECT %02x\n", all, story, ns, rows);
    svLvPut(&g, L, all, rows);
    // карточки, осы, гэги уровня — так же, как svDevCollect на загруженном уровне
    Collect c; memset(&c, 0, sizeof c);
    if (L == 1) snprintf(p, sizeof p, "%s/collect-l1.shr", argv[1]); else snprintf(p, sizeof p, "%s/l%d/collect-l%d.shr", argv[1], L, L);
    size_t cn; void *cb = slurp(p, &cn);
    if (!cb || collectInit(&c, cb, (unsigned)cn)) { fprintf(stderr, "L%d: collect %s не открылся\n", L, p); return 1; }
    c.level = L; svDevCollect(&c);
    g.cards[L] = (uint8_t)collectCards(&c, L); g.wasps[L] = collectWasps(&c, L); g.gags[L] = collectGags(&c, L);
    printf("   карточек %u (маска %02x), ос %u (маска %x), гэгов %u (маска %llx)\n", c.ncard, g.cards[L], c.nwasp, g.wasps[L], c.ngag, (unsigned long long)g.gags[L]);
    g.owned[L] = 0xffff;
    if (L == 7) { g.level = 7; g.msnLevel = 7; g.msnCompleted = all; g.msnStory = (uint8_t)(getenv("SV_STORY") ? atoi(getenv("SV_STORY")) : (ns ? st[ns - 1] : 0));   /* последняя сюжетная миссия (L7 m6): фаза 0, этап 0 — не m7 «конец игры» (TRANSITION|GAMEOVER), её старт сразу даёт титры */ }
  }
  g.ext[SV_EXT_TICKET] = SV_EXT_TICKET_SET | 7;   // вступление, билет, допуск: ticket.c
  uint8_t out[SV_BYTES]; svWrite(&g, out); SaveGame back; if (svRead(out, SV_BYTES, &back) != SV_OK) { fprintf(stderr, "запись не читается\n"); return 1; }
  FILE *f = fopen(argv[3], "wb"); fwrite(out, 1, SV_BYTES, f); fclose(f); printf("записано %s (%d байт), svLvReached=%d\n", argv[3], SV_BYTES, svLvReached(&back));
  return 0;
}
