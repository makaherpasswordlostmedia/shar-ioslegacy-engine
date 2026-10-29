// №339 (остаток: «узкие места забор + дерево/ящик, где можно въехать и не выехать»: J9-9, K11-1, M4-4, F11-9 и др.): рой в прямоугольнике уровня.
// Случайный старт на земле (курс, 8…25 м/с), 3…5 с случайной езды (макросы газ/назад + руль), затем если машина замерла (< 1,5 м/с последнюю секунду): проба тупика
// как tests/pockets/host.c (trappedAt: 8 заходов по 2,5 с, ни один не отъехал на 3 м) и выезд (escapeAt: 8 заходов по 8 с, ни один не ушёл на 15 м). Карман = и то, и то.
// cc -std=c11 -O2 -Iviewer tests/walls687/trap_swarm.c viewer/car.c viewer/col.c -lm ; ./a.out level.shr x0 z0 x1 z1 [N] [seed]
// Печать: строка на карман (старт, курс, скорость, место остановки, причина), итог «карманов k из N».
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W;
static void step(Car *c, float thr, float brk, float st) { CarInput in = {thr, brk, st, 0}; carUpdate(c, &W, &in, 1.f / 60.f); }
static int trappedAt(const Car *c0) {
  static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
  for (int d = 0; d < 8; d++) { Car c = *c0;
    for (int f = 0; f < 150; f++) { int rev = d >= 3 && d < 6 ? 1 : d >= 6 && f < 45; float st = d >= 6 && f < 45 ? -steer[d] : steer[d]; step(&c, rev ? 0.f : 1.f, rev ? 1.f : 0.f, st); }
    if (c.destroyed || hypotf(c.x - c0->x, c.z - c0->z) > 3.f) return 0; }
  return 1;
}
static int escapeAt(const Car *c0) {
  static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
  for (int d = 0; d < 8; d++) { Car c = *c0;
    for (int f = 0; f < 480; f++) { int rev = d >= 3 && d < 6 ? 1 : d >= 6 && f < 45; float st = d >= 6 && f < 45 ? -steer[d] : steer[d]; step(&c, rev ? 0.f : 1.f, rev ? 1.f : 0.f, st); if (c.destroyed) break;
      if (hypotf(c.x - c0->x, c.z - c0->z) > 15.f) return 1; } }
  return 0;
}
static unsigned rs = 99u; static float rnd(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return (rs & 0xffffff) / 16777216.f; }
int main(int argc, char **argv) {
  if (argc < 6) return 2; FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); unsigned n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != n) return 2; fclose(f);
  unsigned co = *(unsigned *)(b + 92), po = *(unsigned *)(b + 96), pv = *(unsigned *)(b + 88), end = n; if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  if (colInit(&W, b + co, end - co)) return 2;
  float x0 = atof(argv[2]), z0 = atof(argv[3]), x1 = atof(argv[4]), z1 = atof(argv[5]); int N = argc > 6 ? atoi(argv[6]) : 400; if (argc > 7) rs = (unsigned)atoi(argv[7]) * 2654435761u | 1u;
  CarParams p; carParamsFor("famil_v", &p); int trapped = 0, runs = 0, stopped = 0, dumped = 0, perch = 0;
  for (int t = 0; t < N; t++) {
    float x = x0 + rnd() * (x1 - x0), z = z0 + rnd() * (z1 - z0), g; if (!colGround(&W, x, z, 30, -20, &g, 0)) continue;
    float h = rnd() * 6.2832f, v = 8 + rnd() * 17; Car c; carInit(&c, &p, &W, x, g, z, h); for (int k = 0; k < 20; k++) step(&c, 0, 0, 0); if (hypotf(c.x - x, c.z - z) > 1.f) continue;
    carSetSpeed(&c, v); runs++; int rec0 = c.recoveries; float secs = getenv("TS_SECS") ? atof(getenv("TS_SECS")) * (0.6f + 0.8f * rnd()) : 3 + rnd() * 2; int frames = (int)(secs * 60), left = 0; float st = 0; int rev = 0; float slow = 0;
    for (int fr = 0; fr < frames + 60 && !c.destroyed; fr++) {
      if (--left <= 0) { left = 45 + (int)(rnd() * 90); st = (rnd() - .5f) * 2.f; rev = rnd() < .15f; } step(&c, rev ? 0.f : 1.f, rev ? 1.f : 0.f, st); }
    if (c.perchEsc) { perch++; printf("ВЫВОД с кромки: старт (%.1f %.1f) → (%.1f %.1f y %.1f) раз %d\n", x, z, c.x, c.z, c.y, c.perchEsc); }
    if (c.destroyed || c.recoveries != rec0) continue;
    float v1 = hypotf(c.vel[0], c.vel[2]); if (v1 > 1.5f) continue; stopped++;
    { const char *tg = getenv("TS_TARGET"); if (tg) { float a, b, cc_, d, y0, y1; sscanf(tg, "%f,%f,%f,%f,%f,%f", &a, &b, &cc_, &d, &y0, &y1); if (!(c.x >= a && c.x <= cc_ && c.z >= b && c.z <= d && c.y >= y0 && c.y <= y1)) continue; } }
    if (!trappedAt(&c)) continue; if (escapeAt(&c)) continue;
    trapped++; if (getenv("TS_DUMP") && !dumped) { FILE *o = fopen(getenv("TS_DUMP"), "wb"); fwrite(&c, sizeof c, 1, o); fclose(o); dumped = 1; }
    printf("КАРМАН старт (%.1f %.1f) курс %.0f° v %.0f → стоит (%.1f %.1f y %.1f), reverts %d\n", x, z, h * 57.3f, v, c.x, c.z, c.y, c.reverts); }
  printf("RESULT карманов %d из %d заходов (остановились %d), выводов с кромки %d\n", trapped, runs, stopped, perch); return 0; }
