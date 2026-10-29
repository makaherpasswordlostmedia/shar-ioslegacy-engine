#ifndef SHAR_CARCOINS_H
#define SHAR_CARCOINS_H
#include "car.h"
#include "coins.h"
#ifndef CAR_BOOM_COINS_OLD
#define CAR_BOOM_COINS_OLD 0
#endif
// PS2 a355_boom: wallet 4 -> 0 at boom, loose coins can be collected again.
// Cap 10 is Rob's explicit fallback rule; direction/speed/lifetime use CoinManager.
// Arm only before the boom, so loading an existing husk is not another penalty.
static inline void carBoomCoins(const Car *car, Coins *coins, const ColWorld *world, int *armed) {
  if (!carBoomed(car)) { *armed = 1; return; }
  if (!*armed) return;
  *armed = 0;
  if (CAR_BOOM_COINS_OLD || !coins || coins->collected <= 0) return;
  int n = coins->collected < 10 ? coins->collected : 10;
  float floor = car->ry;
  if (world) colGround(world, car->x, car->z, car->y + 1.f, car->y - 30.f, &floor, 0);
  coins->collected -= n;
  int automatic = coins->dropAuto;
  coins->dropAuto = 0; // explosion coins scatter for manual pickup, even with no-eject
  coinsDrop(coins, n, car->x, car->y + 1.f, car->z, floor);
  coins->dropAuto = automatic;
}
#endif
