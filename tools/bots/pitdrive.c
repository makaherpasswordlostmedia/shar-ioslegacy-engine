#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
int main(int argc, char **argv) {
  if (bwData(argv[1], argv[2], argv[3])) return 2;
  float x = (float)atof(argv[4]), y = (float)atof(argv[5]), z = (float)atof(argv[6]); int hd = atoi(argv[7]); bwNew(&W);
  bwPlace(&W, x, y, z, hd * 0.3926991f);
  for (int f = 0; f < 200; f++) { bwStep(&W, f < 30 ? 0 : (getenv("PD_BACK") ? GP_L : GP_R), getenv("PD_STEER") ? (float)atof(getenv("PD_STEER")) : 0.f, 0.f);
    if (f % 20 == 0 || f == 29) printf("f%3d pos %.2f %.2f %.2f v %.2f vy %.2f grounded %d wheels %d comp %.3f %.3f %.3f %.3f contacts %d bodyHit %d pen %.3f slip %d airT %.2f noGroundT %.2f embedT %.2f nofitT %.2f bellyT %.2f reverts %d recov %d revWhy %d crashes %d up? supOn? hull?\n", f, W.car.x, W.car.y, W.car.z, W.car.v, W.car.vy, W.car.grounded, W.car.wheels, W.car.comp[0], W.car.comp[1], W.car.comp[2], W.car.comp[3], W.car.contacts, W.car.bodyHit, W.car.pen, W.car.slip, W.car.airT, W.car.noGroundT, W.car.embedT, W.car.nofitT, W.car.bellyT, W.car.reverts, W.car.recoveries, W.car.revWhy, W.car.crashes); }
  return 0;
}
