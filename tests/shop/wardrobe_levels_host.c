// Actual wardrobe parser/input/preview, shop wallet and Homer controller on Mac.
// Only PSP file APIs, audio and UI-open endpoints are replaced. No renderer claim.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "homer.h"
#include "mission/msn.h"
#include "../../viewer/wardrobe_view.c"
static int fails, uiOpen;
static void ck(const char *label, int ok) { printf("CHECK %s %s\n", label, ok ? "OK" : "FAIL"); if (!ok) fails++; }
int uiScrReady(void) { return uiOpen; }
int uiScrOpen(const char *path) { char magic[4]; FILE *f = fopen(path, "rb"); if (!f) return -1;
  int ok = fread(magic, 1, 4, f) == 4 && !memcmp(magic, "UIP1", 4); fclose(f); uiOpen = ok; return ok ? 0 : -1; }
void uiScrClose(void) { uiOpen = 0; }
int sndReady(void) { return 0; }
int sndId(const char *s) { (void)s; return -1; }
int sndPlay2D(int id, float v) { (void)id; (void)v; return 0; }
int audioTrack(const char *s) { (void)s; return -1; }
void audioMusic(int id, float t) { (void)id; (void)t; }
static void settle(void) { for (int i = 0; i < 30; i++) wardrobeTick(.05f); }
static unsigned fp(const SkinModel *m) { unsigned h = 2166136261u; if (!m) return 0;
  for (unsigned i = 0; i < m->h->size; i++) h = (h ^ m->base[i]) * 16777619u; return h; }
static unsigned wornFp;
static int wear(const char *dir, int k) { char path[512]; snprintf(path, sizeof path, "%s%s", dir, wardrobeFile(k));
  SkinModel *model = skinLoad(path); if (!model) return 0;
  Homer *h = calloc(1, sizeof *h); int ok = h && homerInit(h, model) == 0;
  if (ok) { homerPose(h); wornFp = fp(model);
    for (unsigned j = 0; j < model->h->nJoints; j++) ok = ok && isfinite(h->xf[j].q[0]); }
  free(h); skinFree(model); return ok; }
int main(int argc, char **argv) {
  if (argc != 5) return 2;
  char dir[512]; snprintf(dir, sizeof dir, "%s/", argv[1]); int level = atoi(argv[2]);
  FILE *f = fopen(argv[3], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); size_t size = (size_t)ftell(f); rewind(f); void *pack = malloc(size); fread(pack, 1, size, f); fclose(f);
  MsnFile mf; char err[256]; if (msn_open(&mf, pack, size, err, sizeof err)) { puts(err); return 1; }
  Coins coins = {0}; Shop shop; shopInit(&shop, &coins, level);
  for (int i = 0; i < msn_reward_count(&mf); i++) { MsnReward r; msn_reward_get(&mf, i, &r); shopAddItem(&shop, r.name, r.kind, r.quest, r.price, r.seller); }
  char names[8][32], files[8][32]; int prices[8], count = 0;
  f = fopen(argv[4], "r"); if (!f) return 2;
  while (count < 8 && fscanf(f, "%31s %31s %d", names[count], files[count], &prices[count]) == 3) count++;
  fclose(f); ck("catalog-count", wardrobeInit(dir) == count && count == 4);
  for (int k = 0; k < count; k++) { int item = shopFind(&shop, names[k]);
    ck("catalog-file-name-price", wardrobeFile(k) && !strcmp(wardrobeFile(k), files[k]) && !strcmp(wName[k], names[k]) && wPrice[k] == prices[k]);
    ck("mission-reward", item >= 0 && shop.item[item].kind == SHOP_SKIN && shop.item[item].price == prices[k]); }
  ck("purchase-locators", nspot > 0);
  for (int k = 0; k < nspot; k++) { float p[4]; wardrobeSpot(k, p);
    ck("trigger-inside", wardrobeNear(p[0], p[1], p[2]));
    ck("trigger-outside", !wardrobeNear(p[0] + p[3] + .1f, p[1], p[2]));
    ck("trigger-wrong-floor", !wardrobeNear(p[0], p[1] + 3.1f, p[2])); }
  ck("default-owned", shopOwns(&shop, SHOP_SKIN, names[0]));
  unsigned defaultFp = 0;
  for (int k = 1; k < count; k++) {
    ck("open", wardrobeOpen(&shop, dir, 0) == 0); settle(); defaultFp = fp(pm);
    for (int j = 0; j < k; j++) wardrobeInput(&shop, PSP_CTRL_RIGHT);
    ck("preview-loaded-distinct", pm && pmK == k && fp(pm) != defaultFp && skinFindClip(pm, "loco_idle_rest") >= 0);
    coins.collected = prices[k] - 1; unsigned before = shopOwnedMask(&shop);
    wardrobeInput(&shop, PSP_CTRL_CROSS);
    ck("insufficient-coins", phase == WV_IDLE && chosen == -1 && coins.collected == prices[k] - 1 && shopOwnedMask(&shop) == before);
    coins.collected = prices[k] + 7; wardrobeInput(&shop, PSP_CTRL_CROSS); settle();
    ck("buy-once", coins.collected == 7 && shopOwns(&shop, SHOP_SKIN, names[k]) && shop.buys == (unsigned)k);
    int selected = wardrobeEnd(); ck("chosen-costume", selected == k);
    ck("wear-homer-controller", selected >= 0 && wear(dir, selected) && wornFp != defaultFp);
    printf("WEAR level=%d skin=%d file=%s fingerprint=%08x coins=%d\n", level, k, files[k], wornFp, coins.collected);
    ck("reopen-worn", wardrobeOpen(&shop, dir, selected) == 0 && cur == k); settle();
    unsigned buys = shop.buys; wardrobeInput(&shop, PSP_CTRL_CROSS); settle();
    ck("owned-no-charge", coins.collected == 7 && shop.buys == buys && wardrobeEnd() == k);
    ck("open-default", wardrobeOpen(&shop, dir, 0) == 0); settle(); wardrobeInput(&shop, PSP_CTRL_CROSS); settle();
    selected = wardrobeEnd(); ck("wear-default-free", selected == 0 && wear(dir, selected) && wornFp == defaultFp && coins.collected == 7);
  }
  wardrobeOpen(&shop, dir, 0); settle(); wardrobeInput(&shop, PSP_CTRL_RIGHT); wardrobeInput(&shop, PSP_CTRL_CIRCLE); settle();
  ck("cancel-no-wear", wardrobeEnd() == -1);
  Shop reloaded; shopInit(&reloaded, &coins, level); for (int i = 0; i < msn_reward_count(&mf); i++) { MsnReward r; msn_reward_get(&mf, i, &r); shopAddItem(&reloaded, r.name, r.kind, r.quest, r.price, r.seller); }
  for (int k = 1; k < count; k++) ck("owned-wallet-persists", shopOwns(&reloaded, SHOP_SKIN, names[k]));
  free(pack); printf("RESULT L%d %s failures=%d\n", level, fails ? "FAIL" : "PASS", fails); return fails != 0;
}
