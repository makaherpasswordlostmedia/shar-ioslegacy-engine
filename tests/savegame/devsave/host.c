// Правка Роба 335 (05.10): гейт сохранения разработчика на Маке (tests/savegame/devsave/host.sh) — настоящими модулями движка.
//   host LEVEL.shr HOMER.shr level01.msn [level02.msn ... level07.msn]
// 1) запись DEV (как savemenu.c devFill): формат читается, монеты и купленное всех уровней на месте, seq 0 (RESUME её не берёт)
// 2) загрузка DEV на уровне N (resume.story = GAME_MSN_STORY_DEV, как main.c msnStart): пройдены сюжетные миссии уровня, кроме
//    последней; текущая — последняя (m7), свободная езда у её персонажа; переход m8 (L2/L5/L6/L7) не пройден, бонусные/гонки пройдены с DEV-повтором;
//    за 3 с игры уровень сам не кончается. Ожидание — по сценариям диска (level.mfk AddMission), не по флагам пакета:
//    L1 m0..m6 пройдены, у L2..L7 m1..m6; текущая m7 у всех семи
// Красный: сборка с -DGAME_MSN_DEV=0 (загрузка DEV как прежде) обязана упасть.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "world.h"
#include "savegame.h"
#include "game_msn.h"
#include "mission/msn.h"

static int fails;
static void check(const char *name, int ok, const char *fmt, ...) __attribute__((format(printf, 3, 4)));
static void check(const char *name, int ok, const char *fmt, ...) {
  char d[400]; va_list a; va_start(a, fmt); vsnprintf(d, sizeof d, fmt, a); va_end(a);
  printf("CHECK %-24s %s  %s\n", name, ok ? "OK  " : "FAIL", d); if (!ok) fails++;
}
static unsigned char *readAll(const char *fn, size_t *n) {
  FILE *f = fopen(fn, "rb"); if (!f) return 0;
  fseek(f, 0, SEEK_END); *n = (size_t)ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *b = aligned_alloc(16, (*n + 15) & ~(size_t)15); if (b && fread(b, 1, *n, f) != *n) { free(b); b = 0; }
  fclose(f); return b;
}
static const char *mid(const MsnFile *f, int i) { return i >= 0 && (uint32_t)i < f->nmissions ? msn_str(f, f->missions[i].id) : "-"; }
static int idx(const MsnFile *f, const char *id) {
  for (uint32_t i = 0; i < f->nmissions; i++) if (!strcmp(msn_str(f, f->missions[i].id), id)) return (int)i;
  return -1;
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "host LEVEL.shr HOMER.shr level01.msn [level0N.msn ...]\n"); return 2; }
  // ================================================= запись DEV (поля — как savemenu.c devFill; формат не меняется)
  { SaveGame g, b; uint8_t buf[SV_BYTES]; svClear(&g); g.seq = 0; g.coins = 99999; for (int L = 1; L < SV_LEVELS; L++) g.owned[L] = 0xffff;
    g.year = 2026; g.month = 10; g.day = 5; g.hour = 1; g.minute = 2;
    int w = svWrite(&g, buf), r = svRead(buf, sizeof buf, &b), own = 1;
    for (int L = 1; L < SV_LEVELS; L++) own &= b.owned[L] == 0xffff;
    check("dev.record", w == SV_BYTES && r == SV_OK && b.seq == 0 && b.year == 2026 && b.coins == 99999 && own && b.cards[1] == 0 && !b.wasps[1],
          "чтение %s, seq %u, монеты %d, купленное L1..L7 %s, карточки L1 %x", r == SV_OK ? "OK" : "испорчена", (unsigned)b.seq, (int)b.coins,
          own ? "все" : "не все", b.cards[1]); }

  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  for (int a = 3; a < argc; a++) {
    size_t n; unsigned char *pack = readAll(argv[a], &n);
    if (!pack) { check("dev.pack", 0, "нет %s", argv[a]); continue; }
    static BotWorld W; bwNew(&W);
    MsnFile f; char err[160];
    if (msn_open(&f, pack, n, err, sizeof err)) { check("dev.pack", 0, "%s: %s", argv[a], err); free(pack); bwFree(&W); continue; }
    int L = (int)f.hdr->level;
    MsnProgress q; memset(&q, 0, sizeof q); q.version = 1; q.level = (uint8_t)L; q.story = GAME_MSN_STORY_DEV;
    gameMsnOpenAt(&W.msn, &W.G, pack, n, NULL, &q, err, sizeof err);
    MsnRuntime *rt = &W.msn.rt;
    // ожидание по диску: сюжетные AddMission уровня, без перехода m8 у L2/L5/L6/L7 (одна стадия «timer» + SetLevelOver/SetGameOver)
    char want[160] = "", got[160] = "", open[160] = ""; int k0 = L == 1 ? 0 : 1, okDone = 1;
    for (int k = k0; k <= 6; k++) { char id[8]; snprintf(id, sizeof id, "m%d", k); int i = idx(&f, id);
      okDone &= i >= 0 && (rt->completed >> i & 1u); snprintf(want + strlen(want), sizeof want - strlen(want), "%s ", id); }
    for (uint32_t i = 0; i < f.nmissions && i < 32; i++) {
      if (rt->completed >> i & 1u) snprintf(got + strlen(got), sizeof got - strlen(got), "%s ", mid(&f, (int)i));
      else snprintf(open + strlen(open), sizeof open - strlen(open), "%s ", mid(&f, (int)i));
    }
    int m7 = idx(&f, "m7"), m8 = idx(&f, "m8"), bonusDone = 0, extra = 0;
    for (uint32_t i = 0; i < f.nmissions && i < 32; i++) {
      const char *id = mid(&f, (int)i);
      if ((f.missions[i].flags & MSN_MF_BONUS) && (rt->completed >> i & 1u)) bonusDone++;
      int want_i = 0; for (int k = k0; k <= 6; k++) { char t[8]; snprintf(t, sizeof t, "m%d", k); want_i |= !strcmp(id, t); }
      want_i |= !strcmp(id, "sr1") || !strcmp(id, "sr2") || !strcmp(id, "sr3") || !strcmp(id, "gr1") || !strcmp(id, "bm1");
      if ((rt->completed >> i & 1u) && !want_i) extra++;
    }
    char nm[24]; snprintf(nm, sizeof nm, "dev.L%d.done", L);
    check(nm, okDone && !extra, "ждём пройдены %s; пройдены %s(открыты %s)", want, got, open);
    snprintf(nm, sizeof nm, "dev.L%d.current", L);
    check(nm, m7 >= 0 && rt->cur == m7 && rt->story == m7 && rt->phase == 0 && rt->stage == 0 && msn_free_roam(rt),
          "текущая %s (ждём m7), фаза %d этап %d, свободная езда %d", mid(&f, rt->cur), rt->phase, rt->stage, msn_free_roam(rt));
    snprintf(nm, sizeof nm, "dev.L%d.open", L);
    check(nm, bonusDone == 5 && rt->dev_bonus_replay && (m8 < 0 || !(rt->completed >> m8 & 1u)), "бонусных/гонок пройдено %d (ждём 5), переход m8 %s", bonusDone,
          m8 < 0 ? "нет" : (rt->completed >> m8 & 1u) ? "ПРОЙДЕН" : "не пройден");
    { SaveGame g; svClear(&g); g.coins = 99999; for (int k = 1; k < SV_LEVELS; k++) g.owned[k] = 0xffff;   // как savemenu.c devFill
      svApply(&g, NULL, &W.coins);                                                                       // как main.c saveApply
      const Shop *sh = &W.msn.shop; int cars = 0, skins = 0, own = 0;
      for (int i = 0; i < sh->nitem; i++) { cars += sh->item[i].kind == SHOP_CAR; skins += sh->item[i].kind == SHOP_SKIN;
        own += shopOwns(sh, sh->item[i].kind, sh->item[i].name); }
      snprintf(nm, sizeof nm, "dev.L%d.owned", L);
      check(nm, sh->nitem > 0 && own == sh->nitem && shopCoins(sh) == 99999, "наград уровня %d (машин %d, костюмов %d), принадлежат %d, монет %d",
            sh->nitem, cars, skins, own, shopCoins(sh)); }
    for (int fr = 0; fr < 180; fr++) bwStep(&W, 0, 0.f, 0.f);   // 3 с игры: уровень не кончается сам, миссия та же
    snprintf(nm, sizeof nm, "dev.L%d.stays", L);
    check(nm, rt->status != MSN_LEVEL_DONE && rt->cur == m7, "через 3 с: статус %d, миссия %s", rt->status, mid(&f, rt->cur));
    bwFree(&W); free(pack);
  }
  printf("RESULT %s %d\n", fails ? "FAIL" : "OK", fails);
  return fails ? 1 : 0;
}
