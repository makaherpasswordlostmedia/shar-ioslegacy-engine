// Проба геометрии для гейтов Т1.1 (без игры, только коллизия уровня и bwWhere/bwReachable из tools/bots/world.c).
//   probe LEVEL HOMER --where X Y Z            -> "W\tслой\tопор\tобъект" (ключ кластера: этаж и объект)
//   probe LEVEL HOMER --under X Y Z            -> "U\t1" — под самой точкой земля коллизии в ±0.6 м, иначе "U\t0"
//   probe LEVEL HOMER --pairs N                -> до N строк "P\tax ay az\tbx by bz\tcx cy cz": A — дорога (над ней открыто),
//        B — крыша/эстакада над A не дальше 3 м по плоскости и выше на 3 м и больше, в той же клетке 8 м; C — та же дорога,
//        что A, сбоку в 3 м без стены между; во всех трёх машина стоит свободно и 3 с без ввода никуда не съезжает. Детерминированно (обход сетки 2 м)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static float top(float x, float z) { float y, n[3]; return colGround(bwCol(), x, z, 1e4f, -1e4f, &y, n) ? y : -1e9f; }
static int freeCar(float x, float y, float z) {
  Car c; carInit(&c, NULL, bwCol(), x, y + .5f, z, 0.f); if (fabsf(c.y - y) > 1.f) return 0;
  CarBox b; carBox(&c, &b); colProbeCar(bwCol(), &b); if (b.maxDepth >= .3f) return 0;
  CarInput in; memset(&in, 0, sizeof in); float x0 = c.x, y0 = c.y, z0 = c.z;   // стоит 3 с без ввода и никуда не съехала
  for (int f = 0; f < 180; f++) carUpdate(&c, bwCol(), &in, BW_DT);
  return hypotf(c.x - x0, c.z - z0) < .5f && fabsf(c.y - y0) < .5f;
}
int main(int argc, char **argv) {
  if (argc < 5 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "usage: probe LEVEL HOMER --where X Y Z | --under X Y Z | --pairs N\n"); return 2; }
  if (!strcmp(argv[3], "--where") && argc >= 7) {
    int nl; char obj[16]; int l = bwWhere((float)atof(argv[4]), (float)atof(argv[5]), (float)atof(argv[6]), 1.2f, &nl, obj);
    printf("W\t%d\t%d\t%s\n", l, nl, obj); return 0;
  }
  if (!strcmp(argv[3], "--under") && argc >= 7) {   // гейт tests/falls/void_floor.py: под самой точкой земля коллизии в ±0.6 м
    float x = (float)atof(argv[4]), y = (float)atof(argv[5]), z = (float)atof(argv[6]), g, n[3];
    printf("U\t%d\n", colGround(bwCol(), x, z, y + .6f, y - .6f, &g, n) ? 1 : 0); return 0;
  }
  if (!strcmp(argv[3], "--pairs")) {
    const ColWorld *C = bwCol(); int want = atoi(argv[4]), got = 0;
    for (int gz = 0; gz < C->H * (int)C->cell / 2 && got < want; gz++)
      for (int gx = 0; gx < C->W * (int)C->cell / 2 && got < want; gx++) {
        float bx = C->ox + gx * 2.f + 1.f, bz = C->oz + gz * 2.f + 1.f, by = top(bx, bz); if (by < -1e8f) continue;
        for (int k = 0; k < 8 && got < want; k++) {
          float a = k * .785398f, ax = bx + sinf(a) * 2.5f, az = bz + cosf(a) * 2.5f, ay = top(ax, az);
          if (ay < -1e8f || by - ay < 3.f || floorf(ax / 8.f) != floorf(bx / 8.f) || floorf(az / 8.f) != floorf(bz / 8.f)) continue;
          if (!freeCar(ax, ay, az) || !freeCar(bx, by, bz)) continue;
          for (int j = 0; j < 2; j++) {   // бок о бок (курс 0 — нос в +z): сбоку на 3 м, кузова не перекрываются
            float cx = ax + (j ? -3.f : 3.f), cz = az, cy = top(cx, cz);
            if (fabsf(cy - ay) > .5f || !freeCar(cx, cy, cz) || !bwReachable(ax, ay, az, cx, cy, cz)) continue;
            printf("P\t%.2f %.2f %.2f\t%.2f %.2f %.2f\t%.2f %.2f %.2f\n", ax, ay, az, bx, by, bz, cx, cy, cz); got++; break;
          }
        }
      }
    return got ? 0 : 1;
  }
  return 2;
}
