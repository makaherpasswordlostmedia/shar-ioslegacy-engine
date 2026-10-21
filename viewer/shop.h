// Кошелёк, принадлежность и продавцы машин/костюмов (правки ведущего 29.09, пункты 5–6: покупка Plow King у Барни в m3,
// ставка гонки gr1, машины у Гила). Чистый C99 без PSP: один код для EBOOT (viewer/game_msn.c, вид PurchaseRewards) и ботов.
//
// Данные диска (пакет миссий MSN1, tools/missions/compile.py):
//   rewards.mfk BindReward(имя, p3d, car/skin, quest, уровень, цена, продавец) — на уровне 1: plowk_v 150 «simpson» (Барни),
//     cDuff 125 и cVan 100 «gil», костюмы Гомера 100/125/150 «interior»; quest defaultcar/defaultskin — своё с начала,
//     bonusmission/streetrace — награда миссии (unlock), forsale — покупка
//   leveli.mfk AddPurchaseCarReward(магазин, продавец, модель, локатор, радиус, локатор машины) — где стоит продавец
//     (Барни у заправки: «simpson», barney_loc, 1.3 м), AddPurchaseCarNPCWaypoint — его маршрут
//   ставка гонки: SetRaceEnteryFee / цель coins (SetCoinFee) рантайма — MSN_EV_PAY (минус ставка), победа — MSN_EV_MISSION_COMPLETE
//     с квестом 3 (gamble) и суммой (ставка ×2)
// Правила порта (в данных нет; сверить с эталоном PS2):
//   говорить с продавцом — пешком, △ ближе радиуса AddPurchaseCarReward + SHOP_REACH; в машине не продаёт
//   каталог продавца — BindReward forsale с его магазином, в порядке файла; уже купленное показывается, но не покупается
//   кошелёк — счётчик монет мира (Coins.collected), как в оригинале один на всю игру
#ifndef SHOP_H
#define SHOP_H
#include <stdint.h>
#include "coins.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SHOP_ITEMS 32          // BindReward одного уровня (уровень 1: 13)
#define SHOP_SELLERS 4
#define SHOP_REACH 1.2f        // м к радиусу продавца из данных (1.3 м): △ стоя рядом, не вплотную
enum { SHOP_CAR = 1, SHOP_SKIN = 2 };                 // = MSN_OWN_CAR / MSN_OWN_SKIN
enum { SHOP_OK = 0, SHOP_NOMONEY = -1, SHOP_OWNED = -2, SHOP_BAD = -3 };

typedef struct {
  char name[16], seller[16], quest[16];
  int kind, price;
  float attr[4]; int hasAttr;  // rewards.mfk SetCarAttributes: скорость, разгон, прочность, управление (звёзды 0..5 с половинками)
} ShopItem;

typedef struct {
  char shop[16], npc[16];      // магазин ("simpson", "gil"), продавец ("barney")
  float x, y, z, radius;       // локатор продавца и радиус разговора (AddPurchaseCarReward)
  float car[3]; int hasCar;    // где стоит машина на продажу (последний локатор)
} ShopSeller;

typedef struct {
  ShopItem item[SHOP_ITEMS]; int nitem;
  uint32_t ownedLocal;         // без кошелька (Coins) — принадлежность здесь; с ним — Coins.owned[level] (сохраняется: savegame v2)
  int level;
  ShopSeller seller[SHOP_SELLERS]; int nseller;
  Coins *coins; int wallet;    // кошелёк: coins->collected, без монет мира — wallet
  // открытая лавка (вид — экран PurchaseRewards): продавец, выбранный предмет его каталога
  int open, at, sel;
  int lastDelta, lastWhy, spent, earned;   // журнал: последнее изменение кошелька и суммы (тесты, smoke)
  unsigned buys;
} Shop;

void shopInit(Shop *s, Coins *coins, int level);              // пусто: предметов/продавцов нет; купленное — в coins->owned[level]
uint32_t shopOwnedMask(const Shop *s);                         // бит i — предмет i куплен/получен
int  shopAddItem(Shop *s, const char *name, int kind, const char *quest, int price, const char *seller);   // -> индекс или -1
void shopAddSeller(Shop *s, const char *shop, const char *npc, float x, float y, float z, float radius, const float *car);
int  shopFind(const Shop *s, const char *name);               // индекс или -1
int  shopOwns(const Shop *s, int kind, const char *name);      // куплено / получено / своё с начала (defaultcar, defaultskin)
void shopGive(Shop *s, const char *name);                      // награда миссии (bonusmission, streetrace): принадлежит
int  shopCoins(const Shop *s);
void shopCoinsAdd(Shop *s, int delta, int why);                // минус — списать (не ниже 0)
int  shopBuy(Shop *s, int item);                               // SHOP_OK / NOMONEY / OWNED / BAD; списывает цену
// лавка: продавец ближе радиуса к точке игрока (пешком) -> номер или -1
int  shopSellerNear(const Shop *s, float x, float y, float z);
int  shopSellerItem(const Shop *s, int seller, int k);         // k-й предмет каталога продавца -> индекс предмета или -1
int  shopSellerCount(const Shop *s, int seller);
void shopStep(Shop *s, int dir);                               // открытая лавка: ◄ (-1) / ► (+1) по кругу каталога продавца
void shopSetAttr(Shop *s, const char *name, const float a[4]); // SetCarAttributes (звёзды экрана покупки)
// номер машины среди машин на продажу уровня (BindReward forsale car по порядку) = поле ROW0 экрана purchase
// (tools/shop_export.py: имя и цена — варианты строк в том же порядке) -> 0.. или -1
int  shopForsaleCar(const Shop *s, int item);
int  shopStars(const Shop *s, int item, int k);                // полузвёзды 0..10 строки k (0 скорость .. 3 управление), -1 нет данных

#ifdef __cplusplus
}
#endif
#endif
