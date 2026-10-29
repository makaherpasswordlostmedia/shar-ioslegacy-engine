// Контакт двух машин у стены на реальной коллизии уровня (пункт 6 docs/handoff/LOOP_TERMINAL.md).
// Места — три повтора роя (пакет build/sandbox/batches/20260927-172953-2e4b78: seed 104 машины 13/94 у (449,-453),
// seed 105 машины 2/30 у (178,181), seed 105 машины 53/34 у (19,178)). В каждом месте ищем стену: от точки идём по 16
// направлениям, пока кузов не коснётся мира (стена, а не столб: касание и в 2 м вдоль неё). Машина A стоит боком у стены, B давит её в стену на газу:
// скорость 21/30/39 км/ч (±30%), курс B от нормали стены −20°/0/+20°. 90 тиков по 1/60 с тем же порядком, что в
// полигоне: carUpdate обеих → carHitCar → проба мира. «Устойчивое проникновение» — как у роя: кузов в мире глубже
// 0.15 м 12 тиков подряд. Старый код раздвигает пару без взгляда на мир и вдавливает A в стену.
//   tests/carpair/host.sh [level.shr]    CAR_C=… — другая версия car.c (отрицательный контроль)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"

static ColWorld world;
static int fails;
static void check(const char *name, int ok) { printf("%s %s\n", ok ? "OK" : "FAIL", name); fails += !ok; }
static float depthAt(const Car *c) { CarBox b; carBox(c, &b); colProbeCar(&world, &b); return b.maxDepth; }

// стена у точки: кузов на опоре в точке, ведём его по направлению до первого касания мира; нормаль — от стены к машине
static int findWall(float px, float py, float pz, int dir, float *qx, float *qy, float *qz, float *nx, float *nz) {
  float a = dir * 0.19635f, ux = sinf(a), uz = cosf(a), g;
  if (!colGround(&world, px, pz, py + 3.f, py - 6.f, &g, 0)) return 0;
  Car c; memset(&c, 0, sizeof c); carDefaults(&c.p);
  for (float r = 0.f; r < 25.f; r += 0.1f) {
    c.x = px + ux * r; c.z = pz + uz * r; c.h = atan2f(-uz, ux);   // боком к направлению поиска
    c.q[0] = cosf(c.h * .5f); c.q[1] = 0; c.q[2] = sinf(c.h * .5f); c.q[3] = 0;
    float gy; if (!colGround(&world, c.x, c.z, g + 1.5f, g - 3.f, &gy, 0)) return 0;   // съехали с опоры — не то место
    c.y = gy;
    CarBox b; carBox(&c, &b);
    if (colProbeCar(&world, &b) && b.maxDepth > 0.01f) {
      float mx = 0, mz = 0; for (int k = 0; k < b.n; k++) { mx += b.nx[k]; mz += b.nz[k]; }
      float l = hypotf(mx, mz); if (l < 1e-3f) return 0;
      *nx = mx / l; *nz = mz / l;
      if (*nx * ux + *nz * uz > -0.5f) return 0;                     // стена должна стоять поперёк пути
      for (int sgn = -1; sgn <= 1; sgn += 2) {                        // стена, а не столб: касание и на 2 м вдоль неё
        Car e = c; e.x += -*nz * 2.f * sgn; e.z += *nx * 2.f * sgn;
        CarBox eb; carBox(&e, &eb); if (!colProbeCar(&world, &eb) || eb.maxDepth < 0.005f) return 0;
      }
      *qx = c.x - ux * 0.3f; *qz = c.z - uz * 0.3f; *qy = gy;       // отступ, чтобы A стояла, касаясь стены
      return 1;
    }
    g = gy;
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15);
  if (!data || fread(data, 1, size, f) != (size_t)size) return 2;
  fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co)) return 2;
  const float P[3][3] = {{449, 1, -453}, {178, 5, 181}, {19, 4, 178}};
  const float dt = 1 / 60.f;
  int places = 0, cases = 0, persistent = 0, pushedThrough = 0;
  for (int p = 0; p < 3; p++) {
    int walls = 0;
    for (int dir = 0; dir < 32 && walls < 2; dir++) {
      float qx, qy, qz, nx, nz;
      if (!findWall(P[p][0], P[p][1], P[p][2], dir, &qx, &qy, &qz, &nx, &nz)) continue;
      walls++;
      int bad = 0;
      for (int si = -1; si <= 1; si++) for (int ai = -1; ai <= 1; ai++) {
        Car A, B;
        float hA = atan2f(-nz, nx);                                    // A боком к стене (вперёд вдоль стены)
        carInit(&A, NULL, &world, qx, qy, qz, hA);
        for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&A, &world, &in, dt); }
        float hB = atan2f(-nx, -nz) + ai * 0.349f;                     // B смотрит в стену ±20°
        float bx = A.x + nx * (A.p.halfW + 2.5f), bz = A.z + nz * (A.p.halfW + 2.5f), gb;
        if (!colGround(&world, bx, bz, A.y + 2.f, A.y - 3.f, &gb, 0)) continue;
        carInit(&B, NULL, &world, bx, gb, bz, hB);
        for (int k = 0; k < 10; k++) { CarInput in = {0}; carUpdate(&B, &world, &in, dt); }
        float kmh = 30.f * (1.f + 0.3f * si);
        carSetSpeed(&B, kmh / 3.6f);
        int pen = 0, worst = 0; float side0 = (A.x - qx) * nx + (A.z - qz) * nz, minSide = 1e9f;
        for (int t = 0; t < 90; t++) {
          CarInput ia = {0}, ib = {0}; ib.throttle = 1.f;
          carUpdate(&A, &world, &ia, dt); carUpdate(&B, &world, &ib, dt);
#ifdef CARHIT2
          carHitCar(&A, &B);                                            // старая подпись (отрицательный контроль)
#else
          carHitCar(&A, &B, &world);
#endif
          float d = fmaxf(depthAt(&A), depthAt(&B));
          pen = d > 0.15f ? pen + 1 : 0; if (pen > worst) worst = pen;
          float side = (A.x - qx) * nx + (A.z - qz) * nz; if (side < minSide) minSide = side;
        }
        cases++;
        if (worst >= 12) { persistent++; bad++; }
        if (minSide < side0 - 1.5f) pushedThrough++;                   // A ушла за стену дальше, чем на 1.5 м
      }
      printf("place %d (%.0f %.0f): wall n (%.2f %.2f) at (%.1f %.1f) — persistent penetrations %d of 9\n",
             p + 1, P[p][0], P[p][2], nx, nz, qx, qz, bad);
    }
    places += walls > 0;
  }
  printf("places %d/3, cases %d, persistent penetrations %d, pushed through a wall %d\n", places, cases, persistent, pushedThrough);
  check("all three replay places have a wall scene", places == 3);
  check("no persistent penetration when a car shoves another into a wall", persistent == 0);
  // «ушла за стену на 1.5 м» — только наблюдение: одинаково у старого и нового car.c (у (179.7, 183.6) препятствие
  // переезжается, земля за ним на той же высоте), к разведению пары не относится
  printf("note: moved past the contact line by > 1.5 m in %d cases (observation, not a gate)\n", pushedThrough);
  printf("RESULT: %s (%d failures)\n", fails ? "FAIL" : "OK", fails);
  return fails ? 1 : 0;
}
