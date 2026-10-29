// Отсчёт 3-2-1 (отзыв Роба 28.09): в гонке sr1 Милхауса (AddToCountdownSequence в скрипте) игрок держит газ и руль весь
// отсчёт — машина обязана стоять (сдвиг до GO <= 0.3 м), а после GO — поехать (управление вернулось). Игра без экрана,
// код логики общий с EBOOT (viewer/game_msn.c: gameMsnFreezePad / gameMsnFreezeCar, как в main.c).
//   cdfreeze LEVEL HOMER MSN   -> строки "C ..." и "RESULT OK|FAIL" (tests/missions/countdown.sh)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"

static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "cdfreeze: нет данных\n"); return 2; }
  bwNew(&W);
  if (!W.haveMsn) { fprintf(stderr, "cdfreeze: нет миссий\n"); return 2; }
  int mi = msn_find_mission(&W.msn.f, "sr1");
  if (mi < 0 || !msn_start_bonus(&W.msn.rt, mi)) { fprintf(stderr, "cdfreeze: sr1 не запускается\n"); return 2; }
  int f = 0;
  while (W.msn.rt.status != MSN_COUNTDOWN && f < 60 * 20) { bwStep(&W, 0, 0, 0); f++; }   // вступление (диалог) до отсчёта
  if (W.msn.rt.status != MSN_COUNTDOWN) { printf("C отсчёт не начался\nRESULT FAIL\n"); return 1; }
  float x0 = W.car.x, z0 = W.car.z, dmax = 0.f; int cf = 0;
  while (W.msn.rt.status == MSN_COUNTDOWN && cf < 60 * 10) {   // весь отсчёт: газ + руль вправо
    bwStep(&W, GP_R | GP_RIGHT, 1.f, 0.f); cf++;
    float d = hypotf(W.car.x - x0, W.car.z - z0); if (d > dmax) dmax = d;
  }
  float xg = W.car.x, zg = W.car.z;
  for (int k = 0; k < 120; k++) bwStep(&W, GP_R, 0.f, 0.f);   // после GO: газ 2 с
  float after = hypotf(W.car.x - xg, W.car.z - zg);
  int freezeOk = dmax <= .3f, driveOk = after > 1.f;
  printf("C отсчёт %.1f с (%d шагов в скрипте), сдвиг машины до GO %.3f м (можно <= 0.30) -> %s\n", cf / 60.f, W.msn.rt.cd_count, dmax, freezeOk ? "ok" : "FAIL");
  printf("C после GO газ 2 с: проехала %.1f м -> %s\n", after, driveOk ? "ok" : "FAIL");
  printf("RESULT %s\n", freezeOk && driveOk ? "OK" : "FAIL");
  return freezeOk && driveOk ? 0 : 1;
}
