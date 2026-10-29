// resetroad — хост-проверка RESET CAR по дорогам (RESET_ROAD_OLD, game.c gameReset): машина ставится в точку (карман), 1 с стоит, START, 1 с;
// печатается расстояние до оси ближней полосы и сдвиг. Новый код обязан поставить на полосу (<= 3 м), прежний (gameResetRoadOld = 1) остаётся на месте.
//   resetroad LEVEL PLAYER MSN x z [x z ...]    -> строки RR<TAB>x z<TAB>прежний: до полосы м, сдвиг м<TAB>новый: до полосы м, сдвиг м, курс-полосы-разница°
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"
#include "msncar.h"
static BotWorld W; static BotSnap S;
static void one(float x, float z, int old, float *dl, float *mv, float *hd) {
  bwLoad(&W, &S); gameResetRoadOld = old; float gy; if (!colGround(bwCol(), x, z, 60.f, -1e6f, &gy, 0)) gy = 0.f;
  bwPlace(&W, x, gy + .3f, z, 0.f); for (int f = 0; f < 60; f++) bwStep(&W, 0, 0.f, 0.f);
  float x0 = W.car.x, z0 = W.car.z; bwStep(&W, GP_START, 0.f, 0.f); for (int f = 0; f < 60; f++) bwStep(&W, 0, 0.f, 0.f);
  *dl = mcLaneDist((const Traffic *)bwTraffic(), W.car.x, W.car.z); *mv = hypotf(W.car.x - x0, W.car.z - z0); *hd = 0.f;
}
int main(int argc, char **argv) {
  if (argc < 6 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "usage: resetroad LEVEL PLAYER MSN x z ...\n"); return 2; }
  bwNew(&W); bwSaveAlloc(&W, &S); bwSave(&W, &S); int bad = 0;
  for (int i = 4; i + 1 < argc; i += 2) { float x = (float)atof(argv[i]), z = (float)atof(argv[i + 1]), a, b, c, d, e, f;
    one(x, z, 1, &a, &b, &c); one(x, z, 0, &d, &e, &f);
    printf("RR\t%.0f %.0f\tпрежний: до полосы %.1f м, сдвиг %.1f м\tновый: до полосы %.1f м, сдвиг %.1f м\n", x, z, a, b, d, e);
    if (d > 3.f) bad++; }
  printf("RRSUM\t%s\n", bad ? "FAIL (новый не на полосе)" : "PASS");
  return bad ? 1 : 0;
}
