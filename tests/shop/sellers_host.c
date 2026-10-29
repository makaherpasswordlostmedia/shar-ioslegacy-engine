// Правка 140 (Роб 01.10: «некоторых продавцов машин нет вообще»): продавцы машин уровня 1 — в списке персонажей и с моделью,
// когда Гомер рядом. Игра без экрана (tools/bots/world.c) с настоящим рантаймом миссий и viewer/game_msn.c. Координат руками
// нет: продавцы и их места — из AddPurchaseCarReward пакета миссий (лавки viewer/shop.c из того же вызова).
//   list  — после старта уровня Барни («simpson») и Гил («gil») в списке персонажей GameNpc на месте своей лавки или на пути
//           к своей точке маршрута (±0,1 м)
//   near  — у каждого продавца (Гомер в 2 м) он среди моделей не миссионных (gameMsnAmbWant, 2 слота, как NMODEL_AMB вида)
//   far   — в 200 м от всех продавцов (спавн уровня) им модель не положена: слоты — ближним
// Красные (tests/shop/sellers.sh): -DGAME_PLACE_NPC=0 (продавец не в списке) и -DGAME_AMB_SCRIPT_ORDER (модели по порядку скрипта)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"

static int fails;
static void check(const char *name, int ok, const char *d) { printf("CHECK %-6s %s  %s\n", name, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static BotWorld W;

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "sellers_host LEVEL.shr HOMER.shr level01.msn\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  bwNew(&W); for (int f = 0; f < 60; f++) bwStep(&W, 0, 0, 0);
  const GameMsn *M = &W.msn; const Shop *S = &M->shop; char d[400]; int n = 0;
  printf("персонажей %d:", M->nnpc); for (int i = 0; i < M->nnpc; i++) printf(" %s/%d", M->npc[i].name, M->npc[i].kind); printf("\n");
  const char *shops[2] = {"simpson", "gil"};
  for (int s = 0; s < 2; s++) {
    int si = -1; for (int i = 0; i < S->nseller; i++) if (!strcmp(S->seller[i].shop, shops[s])) si = i;
    if (si < 0) { snprintf(d, sizeof d, "лавки %s нет в данных", shops[s]); check("list", 0, d); continue; }
    const ShopSeller *L = &S->seller[si]; const GameNpc *c = gameMsnNpc(M, L->npc);
    // на месте лавки или на пути к своей точке (AddPurchaseCarNPCWaypoint: идёт к ней с первого кадра): отрезок место -> точка, ±0,1 м
    float ax = L->x, az = L->z, bx = c && c->nwp ? c->wp[c->nwp - 1].x : ax, bz = c && c->nwp ? c->wp[c->nwp - 1].z : az, off = 1e9f;
    if (c) { float ux = bx - ax, uz = bz - az, l2 = ux * ux + uz * uz, t = l2 > 1e-6f ? ((c->pos.x - ax) * ux + (c->pos.z - az) * uz) / l2 : 0.f;
      t = t < 0.f ? 0.f : t > 1.f ? 1.f : t; off = hypotf(c->pos.x - ax - ux * t, c->pos.z - az - uz * t); }
    int ok = c && c->kind == MSN_NPC_PLACE && off < .1f && fabsf(c->pos.y - L->y) < .2f;
    snprintf(d, sizeof d, "%s (лавка %s) %s: %.2f %.2f %.2f, лавка %.2f %.2f %.2f, маршрут %d", L->npc, shops[s], c ? "в списке" : "НЕТ в списке",
             c ? c->pos.x : 0.f, c ? c->pos.y : 0.f, c ? c->pos.z : 0.f, L->x, L->y, L->z, c ? c->nwp : -1); check("list", ok, d); n += ok;
    int want[2], nw = gameMsnAmbWant(M, L->x + 2.f, L->y, L->z, 2, want), got = 0;
    for (int j = 0; j < nw; j++) if (c && &M->npc[want[j]] == c) got = 1;
    snprintf(d, sizeof d, "Гомер у %s: модели %s %s", L->npc, nw > 0 ? M->npc[want[0]].name : "-", nw > 1 ? M->npc[want[1]].name : "-");
    check("near", got, d);
  }
  { const Homer *H = &W.homer; int want[2], nw = gameMsnAmbWant(M, H->x, H->y, H->z, 2, want), bad = 0;
    for (int j = 0; j < nw; j++) if (M->npc[want[j]].kind == MSN_NPC_PLACE && hypotf(M->npc[want[j]].pos.x - H->x, M->npc[want[j]].pos.z - H->z) > GAME_AMB_NEAR) bad = 1;
    snprintf(d, sizeof d, "спавн (%.0f, %.0f): модели %s %s", H->x, H->z, nw > 0 ? M->npc[want[0]].name : "-", nw > 1 ? M->npc[want[1]].name : "-");
    check("far", !bad, d); }
  printf("RESULT %s продавцов в списке %d/2, провалов %d\n", fails ? "FAIL" : "PASS", n, fails);
  return fails ? 1 : 0;
}
