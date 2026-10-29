// Гейт «машина уровня в движке» (tests/cars/cars.sh): что движок берёт из CAR1 level.shr — тем же кодом viewer/car.c
// (carParamsFromCar1 -> carParamsFor(.con из carparams.h) + кузов, посадка, камера CAR1 v2). Печатает поля CarParams
// строками «имя значение»; сверку с диском делает tests/cars/car_check.py.
//   params_host LEVEL.shr        машина уровня
//   params_host --defaults       carDefaults (famil_v до 29.09) — эталон уровня 1
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "car.h"

static void dump(const CarParams *p, int src) {
  printf("src %d\nname %s\n", src, p->name);
#define F(x) printf(#x " %.9g\n", (double)p->x);
  F(mass) F(gasScale) F(slipGasScale) F(hsGasScale) F(gasSpeedThreshold) F(brakeScale) F(topSpeed) F(maxWheelTurn)
  F(hsSteeringDrop) F(tireGrip) F(normalSteering) F(slipSteering) F(eBrakeEffect) F(slipSteeringNoEBrake) F(slipEffectNoEBrake)
  F(cmX) F(cmY) F(cmZ) F(suspensionLimit) F(springK) F(damperC) F(suspensionYOffset) F(hitPoints) F(burnoutRange) F(donutTorque)
  F(weebleOffset) F(wheelieRange) F(wheelieY) F(wheelieZ)
  F(halfW) F(halfL) F(bodyOfs) F(wheelX) F(wheelF) F(wheelR) F(wheelRad) F(bodyLo) F(bodyHi) F(bandLo) F(bandHi) F(step)
  F(gravity) F(restitution) F(wallFriction) F(groundRestitution) F(groundFriction) F(pop) F(popMax) F(hitY) F(angDamp) F(airLevel)
  F(steerResp) F(reverseSpeed) F(fallReset) F(sub)
  F(seat[0]) F(seat[1]) F(seat[2]) F(seatAx) F(seatAz) F(doorX) F(doorZ) F(camElev) F(camMag)
#undef F
}

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "params_host LEVEL.shr | --defaults\n"); return 2; }
  CarParams p;
  if (!strcmp(argv[1], "--defaults")) { carDefaults(&p); dump(&p, 0); return 0; }
  FILE *f = fopen(argv[1], "rb"); if (!f) { fprintf(stderr, "нет файла %s\n", argv[1]); return 2; }
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *b = malloc((size_t)n); if (!b || fread(b, 1, (size_t)n, f) != (size_t)n) return 2; fclose(f);
  if (n < 104 || memcmp(b, "SHR7", 4)) { fprintf(stderr, "не SHR7\n"); return 2; }
  unsigned c1, pv; memcpy(&c1, b + 100, 4); memcpy(&pv, b + 88, 4);
  unsigned end = (unsigned)n; if (pv > c1 && pv < end) end = pv;
  if (!c1 || c1 >= end) { fprintf(stderr, "нет CAR1\n"); return 2; }
  int r = carParamsFromCar1(b + c1, end - c1, &p);
  dump(&p, r);
  if (r < 0) fprintf(stderr, "CAR1: %s\n", carParamsError(r));
  free(b);
  return 0;
}
