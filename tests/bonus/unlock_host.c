// Actual collectStep + save round-trip + the production unlock helper.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "collect.h"
#include "savegame.h"
#include "bonus_unlock.h"

static unsigned failures, checks;
static void check(int ok, const char *label, int level) {
  checks++;
  if (!ok) { failures++; printf("FAIL %s level=%d\n", label, level); }
}
static void *pack(const char *path, unsigned *size) {
  FILE *f = fopen(path, "rb"); if (!f) return NULL;
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  void *b = aligned_alloc(16, (n + 15) & ~15L);
  if (!b || fread(b, 1, n, f) != (size_t)n) { fclose(f); free(b); return NULL; }
  fclose(f); *size = (unsigned)n; return b;
}
int main(int argc, char **argv) {
  if (argc != 2) return 99;
  SaveGame saved; svClear(&saved);
  check(bonusUnlockMask(saved.cards) == 0, "new game locked", 0);
  check(bonusUnlockMask(NULL) == 0, "missing save locked", 0);
  unsigned completed = 0;
  for (int L = 1; L <= 7; L++) {
    char path[1024]; unsigned size;
    if (L == 1) snprintf(path, sizeof path, "%s/collect-l1.shr", argv[1]);
    else snprintf(path, sizeof path, "%s/l%d/collect-l%d.shr", argv[1], L, L);
    void *data = pack(path, &size); Collect c;
    if (!data || collectInit(&c, data, size)) { printf("FAIL missing/invalid %s\n", path); return 99; }
    check(c.level == L && c.ncard == 7, "disc seven-card deck", L);
    svApply(&saved, &c, NULL);
    check(bonusUnlockMask(c.st.cards) == completed, "previous levels restored", L);
    unsigned done = 0;
    ColWorld world = {0};
    for (unsigned k = 0; k < c.ncard; k++) {
      CollPlayer player = {c.card[k].x, c.card[k].y - .9f, c.card[k].z, 1, -1, 0};
      collectStep(&c, &player, NULL, NULL, &world, NULL, 1.f / 60.f);
      CollEvent event; unsigned got = 0;
      while (collectPop(&c, &event)) { got += event.type == CE_CARD; done += event.type == CE_CARDS_DONE; }
      check(got == 1, "real card event", L);
      check(bonusUnlockMask(c.st.cards) == (k + 1 == c.ncard ? completed | (1u << (L - 1)) : completed), "only full deck unlocks", L);
    }
    check(done == 1, "one full-deck event", L);
    completed |= 1u << (L - 1);
    svCapture(&saved, NULL, &c, NULL);
    unsigned char bytes[SV_BYTES]; SaveGame loaded;
    check(svWrite(&saved, bytes) == SV_BYTES && svRead(bytes, sizeof bytes, &loaded) == SV_OK, "actual save round-trip", L);
    check(bonusUnlockMask(loaded.cards) == completed, "save preserves unlocks", L);
    saved = loaded;
    for (int track = 1; track <= 7; track++) check(bonusTrackOpen(completed, track) == (track <= L), "individual track access", L);
    collectFree(&c); free(data);
  }
  unsigned char dev[8] = {0}; bonusDevCards(dev);
  check(bonusUnlockMask(dev) == 0x7f, "dev all seven", 0);
  check(bonusTrackStep(1, 1, 1) == 1 && bonusTrackStep(1, 1, -1) == 1, "locked tracks skipped", 0);
  check(bonusTrackStep(0x7f, 7, 1) == 1 && bonusTrackStep(0x7f, 1, -1) == 7, "all-open wrap", 0);
  check(bonusTrackPick(0x20, 1) == 6, "pick first available", 0);
  printf("%s bonus unlock checks=%u failures=%u real_cards=49 save_levels=7\n", failures ? "FAIL" : "PASS", checks, failures);
  return failures ? 1 : 0;
}
