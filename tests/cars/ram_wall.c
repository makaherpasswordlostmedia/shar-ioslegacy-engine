// Удар в стену гаража на 19 м/с (К-60, PS2 b2_ram, build/ps2ref/answers/b2_ram/trace.tsv): машина стоит в (215.05, 4.05, -170.25 PS2), ей задаётся
// скорость (5.90; -19.10), через ~18 кадров удар о стену z ≈ -177 (PS2). PS2 за такт: по нормали -18.19 -> +1.73 (отскок ≈0.095), вдоль 5.62 -> 3.06,
// полная остановка за 0.48 с, подброс ≤ 0.06 м. Порт: тот же старт (ось z зеркальна: z порта = -z PS2), машина едет задом (носом от стены), как «задом
// въезжает». cc ... tests/cars/ram_wall.c viewer/car.c viewer/col.c -lm && ./a.out LEVEL.shr [heading_deg_offset]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W; static Car car;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = malloc(n); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  float vx = 5.90f, vz = 19.10f, g; float x0 = 215.05f, z0 = 170.25f;
  if (!colGround(&W, x0, z0, 10.f, -5.f, &g, 0)) { printf("нет земли\n"); return 1; }
  float hoff = argc > 2 ? atof(argv[2]) * 0.0174533f : 0.f;
  carInit(&car, NULL, &W, x0, g + 1.f, z0, atan2f(-vx, -vz) + hoff);   // носом от направления удара (задом)
  for (int k = 0; k < 30; k++) { CarInput in = {0}; carUpdate(&car, &W, &in, 1 / 60.f); }
  float y0 = car.y; car.vel[0] = vx; car.vel[1] = 0.f; car.vel[2] = vz; car.x = x0; car.z = z0;
  float ymax = y0, tstop = -1, tHit = -1, vnBefore = 0, vtBefore = 0, vnAfter = 0, vtAfter = 0;
  for (int fr = 0; fr < 240; fr++) {
    CarInput in = {0}; float pvx = car.vel[0], pvz = car.vel[2]; carUpdate(&car, &W, &in, 1 / 60.f);
    if (tHit < 0 && car.vel[2] < 0.5f * pvz) { tHit = (fr + 1) / 60.f; vnBefore = pvz; vtBefore = pvx; vnAfter = car.vel[2]; vtAfter = car.vel[0]; }
    if (car.y > ymax) ymax = car.y;
    if (tHit >= 0 && tstop < 0 && hypotf(car.vel[0], car.vel[2]) < 0.15f) tstop = (fr + 1) / 60.f - tHit;
    if (fr < 8 + 40 && (fr % 1 == 0) && tHit >= 0 && (fr + 1) / 60.f - tHit < 0.1f) printf("  t+%.3f vel %.2f %.2f speed %.2f\n", (fr + 1) / 60.f - tHit, car.vel[0], car.vel[2], hypotf(car.vel[0], car.vel[2]));
  }
  printf("порт: до удара нормаль %.2f вдоль %.2f -> после нормаль %.2f вдоль %.2f (отскок %.3f), стоп за %.2f с, подброс %.3f м, урон %.2f\n",
         -vnBefore, vtBefore, -vnAfter, vtAfter, vnBefore != 0.f ? vnAfter / vnBefore : 0.f, tstop, ymax - y0, car.damage);
  printf("PS2:  до удара нормаль 18.19 вдоль 5.62 -> после +1.73 / 3.06 (отскок 0.095), стоп 0.48 с, подброс ≤ 0.06 м\n");
  return 0;
}
