/* №517: самый долгий промежуток между вызовами кадра газеты (mcProbePump) во время mcProbeRoads на уровне — мера «провала» экрана загрузки на 25 %.
   Использование: probe_gap level.shr homer.shr level0N.msn; печатает максимум и число вызовов. -DMCPROBE_PUMP_OLD=1 — только между дорогами (красный). */
#include <stdio.h>
#include <time.h>
#include "world.h"
#include "msncar.h"
static double last, maxgap; static unsigned calls;
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e3 + t.tv_nsec * 1e-6; }
static void pump(void) { double n = now(); if (calls && n - last > maxgap) maxgap = n - last; last = n; calls++; }   // первый промежуток (чтение уровня до проверки дорог) не считается
int main(int argc, char **argv) {
  if (argc < 4) return 2;
  mcProbePump = pump; last = now();
  if (bwData(argv[1], argv[2], argv[3])) return 2;
  printf("pump calls %u, max gap %.1f ms\n", calls, maxgap); return 0;
}
