// Кошелёк и продавцы на Маке (пункты 5–6 ведущего 29.09): игра без экрана (tools/bots/world.c) с настоящим рантаймом миссий,
// viewer/game_msn.c и viewer/shop.c. Координат руками нет: продавцы — из AddPurchaseCarReward пакета миссий, цены — BindReward,
// ставка — SetRaceEnteryFee/SetCoinFee гонки gr1.
//   tests/shop/host.sh [--gate]   (сборка; --gate: как есть PASS, сборка -DGAME_SHOP_API=0 обязана упасть)
// Проверки:
//   catalog  — продавцы «simpson» (Барни) и «gil», у Барни plowk_v 150, у Гила cDuff 125 и cVan 100
//   barney   — Гомер пешком у Барни, △ — лавка открыта, X — Plow King куплен: 200 -> 50, принадлежит; второй X — отказ, кошелёк тот же
//   gil      — 100 монет: cDuff (125) — отказ «мало монет», cVan (100) — куплен, кошелёк 0
//   gr1      — ставка: 100 монет, Гомер у Луи, △ — минус 20 (80); круг по точкам гонки (машина ставится в каждую точку,
//              это проверка расчёта, не езды) — победа, плюс 40 (ставка ×2): 120
//   gr1_par  — (30.09, часть race) то же, но 200 с стоять на старте: время вверх (UseElapsedTime) перешло SetParTime 195 —
//              провал «partime», кошелёк остаётся 80 (ставка пропала, выигрыша нет); красный: сборка -DMSN_BREAK_PARTIME=1
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static int fails;
static void check(const char *name, int ok, const char *fmt, ...) __attribute__((format(printf, 3, 4)));
#include <stdarg.h>
static void check(const char *name, int ok, const char *fmt, ...) {
  char d[300]; va_list a; va_start(a, fmt); vsnprintf(d, sizeof d, fmt, a); va_end(a);
  printf("CHECK %-22s %s  %s\n", name, ok ? "OK  " : "FAIL", d); if (!ok) fails++;
}
static BotWorld W;
static void walkTo(float x, float y, float z) {   // Гомер пешком рядом (выход из машины: △ на месте, потом поставить)
  for (int k = 0; k < 200 && !gameOnFoot(&W.G); k++) bwStep(&W, k == 0 ? GP_TRIANGLE : 0, 0, 0);
  homerPlace(&W.homer, bwCol(), x, y + 1.f, z, 0.f); for (int k = 0; k < 10; k++) bwStep(&W, 0, 0, 0);
}
static void press(unsigned b) { bwStep(&W, b, 0, 0); for (int k = 0; k < 5; k++) bwStep(&W, 0, 0, 0); }

// gr1 одним заходом: ставка у Луи (△), потом круг по точкам гонки (машина ставится в каждую точку — проверка расчёта, не езды).
// wait — секунд стоять на старте гонки (UseElapsedTime: время идёт вверх, SetParTime — предел); -> пройдена ли; кошелёк после
// ставки (paid) и в конце (won), причина провала (fl), время (t)
static int gr1Run(float wait, int *paid, int *won, int *fl, float *tt) {
  bwFree(&W); bwNew(&W); for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
  W.coins.collected = 100;
  int mi = msn_find_mission(&W.msn.f, "gr1"); MsnRuntime *rt = &W.msn.rt;
  msn_start_bonus(rt, mi);
  int tries = 0, verbose = getenv("SHOP_V") != 0; float t = 0, raceT = -1.f; *paid = -1; *fl = 0;
  for (int f = 0; f < 60 * 400 && !((rt->completed >> mi) & 1u); f++, t += BW_DT) {
    MsnWorld w; gameMsnWorld(&W.msn, &w); MsnVec3 p;
    if (rt->status == MSN_FAILED) { *fl = rt->fail; break; }
    if (verbose && f % 300 == 0) printf("  t=%.0f статус %d цель %d этап %d.%d кошелёк %d пешком %d таймер %.1f\n", t, rt->status, rt->obj, rt->phase, rt->stage, W.coins.collected, gameOnFoot(&W.G), rt->remaining);
    if (rt->status == MSN_RUNNING && rt->obj == MSN_OBJ_COINS && msn_nav_target(rt, &w, &p)) {   // ставка: подойти к Луи, △
      if (++tries > 20) { printf("  ставка не принята за 20 попыток (цель у %.1f %.1f %.1f)\n", p.x, p.y, p.z); break; }
      walkTo(p.x + .8f, p.y, p.z); press(GP_TRIANGLE); if (*paid < 0 && rt->obj != MSN_OBJ_COINS) *paid = W.coins.collected; continue;
    }
    if (rt->status == MSN_RUNNING && rt->obj == MSN_OBJ_RACE && msn_nav_target(rt, &w, &p)) {       // точка круга: машину в неё
      if (gameOnFoot(&W.G)) { for (int k = 0; k < 400 && gameOnFoot(&W.G); k++) { HomerCar hc; memset(&hc, 0, sizeof hc); homerCarFrom(&hc, &W.car, W.lift);
          if (!homerCanEnter(&W.homer, &hc)) homerPlace(&W.homer, bwCol(), W.car.x - 2.f, W.car.y + 1.f, W.car.z, 0.f);
          bwStep(&W, (k % 20) == 0 ? GP_TRIANGLE : 0, 0, 0); } }
      if (*paid < 0) *paid = W.coins.collected;
      if (raceT < 0.f) raceT = t;
      if (t - raceT < wait) { bwStep(&W, 0, 0, 0); continue; }                                   // стоять на старте
      bwPlace(&W, p.x, p.y + .5f, p.z, W.car.h); bwStep(&W, 0, 0, 0); continue;
    }
    bwStep(&W, 0, 0, 0);
  }
  *won = W.coins.collected; *tt = t;
  return (int)((rt->completed >> mi) & 1u);
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "host LEVEL.shr HOMER.shr level01.msn\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  bwNew(&W); for (int f = 0; f < 60; f++) bwStep(&W, 0, 0, 0);
  Shop *S = &W.msn.shop;
  int si = -1, gi = -1; for (int i = 0; i < S->nseller; i++) { if (!strcmp(S->seller[i].shop, "simpson")) si = i; if (!strcmp(S->seller[i].shop, "gil")) gi = i; }
  int ip = shopFind(S, "plowk_v"), id = shopFind(S, "cDuff"), iv = shopFind(S, "cVan");
  check("catalog", si >= 0 && gi >= 0 && ip >= 0 && S->item[ip].price == 150 && id >= 0 && S->item[id].price == 125 && iv >= 0 && S->item[iv].price == 100 &&
        shopSellerItem(S, si, 0) == ip && shopSellerCount(S, gi) == 2,
        "продавцов %d (Барни %d, Гил %d), предметов %d: plowk_v %d, cDuff %d, cVan %d", S->nseller, si, gi, S->nitem,
        ip >= 0 ? S->item[ip].price : -1, id >= 0 ? S->item[id].price : -1, iv >= 0 ? S->item[iv].price : -1);
  if (si < 0 || gi < 0 || ip < 0) { printf("RESULT FAIL %d\n", fails); return 1; }
  // ---- экран покупки (viewer/shop_view.c): звёзды из SetCarAttributes (полузвёзды) и номер машины = ROW0 пакета shop.shr
  // (tools/shop_export.py: машины на продажу уровня по порядку rewards.mfk). plowk_v 1.5, 0.5, 5, 1.5 (rewards.mfk: скорость, разгон,
  // прочность, управление) -> 3 1 10 3; cVan 1.5 1.5 3.5 3 -> 3 3 7 6
  { int ps[4], vs[4]; for (int k = 0; k < 4; k++) { ps[k] = shopStars(S, ip, k); vs[k] = shopStars(S, iv, k); }
    check("stars", ps[0] == 3 && ps[1] == 1 && ps[2] == 10 && ps[3] == 3 && vs[0] == 3 && vs[1] == 3 && vs[2] == 7 && vs[3] == 6 &&
          shopForsaleCar(S, ip) == 0 && shopForsaleCar(S, id) == 1 && shopForsaleCar(S, iv) == 2 && shopForsaleCar(S, shopFind(S, "famil_v")) == -1,
          "Plow King %d %d %d %d, фургон %d %d %d %d (полузвёзды); номера на экране %d %d %d", ps[0], ps[1], ps[2], ps[3], vs[0], vs[1], vs[2], vs[3],
          shopForsaleCar(S, ip), shopForsaleCar(S, id), shopForsaleCar(S, iv)); }
  printf("SELLER barney %.2f %.2f %.2f r %.2f; gil %.2f %.2f %.2f r %.2f\n", S->seller[si].x, S->seller[si].y, S->seller[si].z, S->seller[si].radius,
         S->seller[gi].x, S->seller[gi].y, S->seller[gi].z, S->seller[gi].radius);
  // ---- Барни
  W.coins.collected = 200; const ShopSeller *B = &S->seller[si];
  walkTo(B->x + 1.f, B->y, B->z);
  int near = gameMsnWantsAction(&W.msn); press(GP_TRIANGLE); int opened = gameShopOpen(&W.msn) == si;
  press(GP_CROSS); int c1 = W.coins.collected, own1 = shopOwns(S, 1, "plowk_v");
  press(GP_CROSS); int c2 = W.coins.collected, den = W.msn.shopDenied;
  press(GP_CIRCLE); int closed = gameShopOpen(&W.msn) < 0;
  check("barney", near && opened && c1 == 50 && own1 && c2 == 50 && den == 1 && closed,
        "△ нужен %d, лавка %d; купил: кошелёк 200 -> %d, Plow King %d; ещё раз: %d (отказов %u); ○ закрыл %d", near, opened, c1, own1, c2, W.msn.shopDenied, closed);
  // ---- Гил
  W.coins.collected = 100; const ShopSeller *Gs = &S->seller[gi];
  walkTo(Gs->x + 1.f, Gs->y, Gs->z); press(GP_TRIANGLE);
  int k1 = -1, k2 = -1; for (int k = 0; k < shopSellerCount(S, gi); k++) { if (shopSellerItem(S, gi, k) == id) k1 = k; if (shopSellerItem(S, gi, k) == iv) k2 = k; }
  while (W.msn.shop.sel != k1 && k1 >= 0) press(GP_RIGHT);
  unsigned d0 = W.msn.shopDenied; press(GP_CROSS); int noMoney = W.msn.shopDenied == d0 + 1 && W.coins.collected == 100 && !shopOwns(S, 1, "cDuff");
  while (W.msn.shop.sel != k2 && k2 >= 0) press(GP_RIGHT);
  press(GP_CROSS); int van = shopOwns(S, 1, "cVan") && W.coins.collected == 0;
  press(GP_TRIANGLE);
  check("gil", gameShopOpen(&W.msn) < 0 && noMoney && van, "cDuff за 125 при 100 — отказ %d; cVan за 100 — куплен %d, кошелёк %d", noMoney, van, W.coins.collected);
  // ---- gr1: ставка и выигрыш; 30.09 (часть race): пар-время SetParTime 195 — опоздал, ставка пропала, выигрыша нет
  int paid, won, fl; float t;
  int done = gr1Run(0.f, &paid, &won, &fl, &t);
  check("gr1", paid == 80 && won == 120 && done, "ставка: 100 -> %d (минус 20), победа: -> %d (плюс 40 = ставка ×2), пройдена %d за %.0f с",
        paid, won, done, t);
  done = gr1Run(200.f, &paid, &won, &fl, &t);
  check("gr1_par", paid == 80 && won == 80 && !done && fl == MSN_FAIL_PARTIME, "200 с на старте при пар-времени 195: провал «%s» на %.0f с, кошелёк %d -> %d (ставка не вернулась), пройдена %d",
        msn_fail_name[fl], t, paid, won, done);
  printf("RESULT %s %d\n", fails ? "FAIL" : "OK", fails);
  return fails ? 1 : 0;
}
