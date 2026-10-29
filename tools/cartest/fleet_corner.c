// Вариант №388: вход в поворот на заданной скорости VT (-DVT=14.f / 20.f), не на максимальной. Остальное как cornering.c
// №406 (Роб 09.10, PSP: «на скорости и в резких поворотах машины отрываются от дороги, будто без массы и инерции,
// переворачиваются»): каждая машина диска (carparams.h carCons) на ровной площадке тем же carUpdate, что в игре.
// Заезд: разгон по прямой полным газом до установившейся скорости, затем полный руль с полным газом (и отдельно — с ручником).
// Печатает по машине: скорость входа, наибольший крен, доля кадров на двух колёсах и меньше, отрыв всех колёс, перевороты.
//   cc -std=c11 -O2 -I viewer tests/cars/cornering.c viewer/car.c viewer/col.c -lm -o cornering && ./cornering [машина] [--max-flips N]
// Гейт матрицы (tests/cars/physics_matrix.sh): --max-flips 7 — уровень прежнего порта a359ccd (7 переворотов / 27 на двух колёсах,
// замер этим же файлом 09.10); красный — физика Fable до 406 (-DCAR_TYRE_LEVER_OLD=1 -DCAR_WEEBLE_GROUND_OLD=1: 78).
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "car.h"
#include "carparams.h"
#ifndef VT
#define VT 14.f
#endif
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } floorData;
int main(int argc, char **argv) {
  memset(&floorData, 0, sizeof floorData); memcpy(floorData.h.magic, "COL1", 4);
  floorData.h.ox = floorData.h.oz = -2000; floorData.h.cell = 4000; floorData.h.W = floorData.h.H = 1; floorData.h.ntri = floorData.h.nref = 2;
  floorData.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}};
  floorData.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  floorData.start[1] = 2; floorData.refs[0] = 0; floorData.refs[1] = 1;
  ColWorld w; if (colInit(&w, &floorData, sizeof floorData)) return 2;
  const char *only = 0; int maxFlips = 0;
  for (int i = 1; i < argc; i++) { if (!strcmp(argv[i], "--max-flips") && i + 1 < argc) maxFlips = atoi(argv[++i]); else only = argv[i]; }
  const float dt = 1.f / 30.f;
  int nflip = 0, ntwo = 0, ncars = 0;
  printf("%-10s %-6s %7s %8s %9s %9s %8s %6s\n", "car", "mode", "v_in", "roll_max", "two_whl%", "air_all%", "rights", "flip");
  for (int m = 0; m < CAR_CONS; m++) {
    if (only && strcmp(only, carCons[m].name)) continue;
    for (int mode = 0; mode < 2; mode++) {   // 0 полный газ + руль, 1 ручник + руль
      CarParams p; if (!carParamsFor(carCons[m].name, &p)) continue;
      Car c; carInit(&c, &p, &w, 0, 0, 0, 0);
      CarInput in = {1.f, 0.f, 0.f, 0.f};
      for (int f = 0; f < 30 * 10; f++) { in.throttle = c.v < VT ? 1.f : 0.f; carUpdate(&c, &w, &in, dt); if (c.v >= VT && f > 30) break; }   // разгон до VT м/с
      in.throttle = 1.f;
      float vin = c.v, rollMax = 0.f; int two = 0, air = 0, n = 0, flip = 0, r0 = c.rights;
      in.steer = 1.f; if (mode) in.handbrake = 1.f;
      for (int f = 0; f < 30 * 6; f++) {
        carUpdate(&c, &w, &in, dt); n++;
        float up = 1.f - 2.f * (c.q[1] * c.q[1] + c.q[3] * c.q[3]);   // ось вверх тела, y
        float roll = fabsf(c.roll) * 57.2958f; if (roll > rollMax) rollMax = roll;
        two += c.wheels <= 2; air += c.wheels == 0;
        if (up < 0.f) flip = 1;
      }
      int rights = c.rights - r0; flip |= rights > 0;
      printf("%-10s %-6s %7.1f %8.1f %9.1f %9.1f %8d %6s\n", carCons[m].name, mode ? "ebrake" : "gas", vin * 3.6f, rollMax,
             100.f * two / n, 100.f * air / n, rights, flip ? "FLIP" : "-");
      nflip += flip; ntwo += two * 10 > n; ncars++;
    }
  }
  printf("RESULT cases %d flips %d two-wheel>10%% %d\n", ncars, nflip, ntwo);
  return nflip > maxFlips ? 1 : 0;
}
