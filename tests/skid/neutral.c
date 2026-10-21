// Правка Роба 424 (09.10: «следы на повороте жёлтые/коричневые — не оставлять контрастные полосы») и ОСТАТОК 09.10 п. 18 (249):
// следы шин — ровный нейтральный цвет skid.bmp диска (среднее 32, 32, 32; альфа × 221/255), и у машины не только в слоте игрока.
// Тот же код машины, коллизии и следов, что на PSP (SKID_HOST), земля у спавна уровня 1. Игрок (слот 0) и машина миссии
// (слот 1) — по очереди резкий тормоз с 15 м/с (как A в tests/skid/host.c). Проверки: у обоих слотов есть следы; цвет вершин каждого квада — 0x202020
// (серый без оттенка: |R−G|, |G−B| = 0); альфа участка торможения ≤ 127 × 221/255 = 110. Красный (tests/skid/neutral.sh):
// -DSKID_TINT_OLD=1 — прежний цвет (a, a, a) × текстура обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "skid.h"
static ColWorld W; static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-8s %s  %s\n", n, ok ? "OK  " : "FAIL", d); fails += !ok; }
#define DT (1 / 60.f)
static void place(Car *c, float x, float z, float h) {
  float g; if (!colGround(&W, x, z, 50, -50, &g, 0)) { printf("нет земли %.1f %.1f\n", x, z); exit(2); }
  carInit(c, NULL, &W, x, g, z, h);
  for (int k = 0; k < 30; k++) { CarInput in = {0, 0, 0, 0}; carUpdate(c, &W, &in, DT); }
}
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) { unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m; }
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) return 2; unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104) return 2;
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned end = (unsigned)ftell(f); if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f); if (!cm || colInit(&W, cm, end - colOff)) return 2;
  skidClear(1);
  for (int slot = 0; slot < 2; slot++) {   // тот же тормоз, что tests/skid/host.c A: 15 м/с, тормоз до остановки; слот 0 — игрок, 1 — машина миссии
    Car c; place(&c, 200.f, 172.f, 1.5708f); carSetSpeed(&c, 15.f);
    for (int k = 0; k < 5; k++) { CarInput in = {0, 0, 0, 0}; carUpdate(&c, &W, &in, DT); skidCar(slot, &c, &in, &W); }
    for (int fr = 0; fr < 600 && sqrtf(c.vel[0] * c.vel[0] + c.vel[2] * c.vel[2]) > .5f; fr++) { CarInput in = {0, 1, 0, 0}; carUpdate(&c, &W, &in, DT); skidCar(slot, &c, &in, &W); }
    for (int k = 0; k < 10; k++) { CarInput in = {0, 0, 0, 0}; carUpdate(&c, &W, &in, DT); skidCar(slot, &c, &in, &W); }
  }
  SkidStat s; skidGetStat(&s);
  int n = 0, bad = 0, amax = 0; unsigned badc = 0; float p[4][3]; unsigned char al[4];
  for (int i = 0; i < SKID_QUADS; i++) {
    if (!skidQuadAt(i, p, al)) continue; n++;
    unsigned c = skidQuadRgb(i), r = c & 255, g = (c >> 8) & 255, bb = (c >> 16) & 255;
    if (c != 0x202020u) { bad++; badc = c; }
    (void)r; (void)g; (void)bb;
  }
  char d[200];
  snprintf(d, sizeof d, "квадов %d, из них машины миссии %d", s.made, s.madeAi); check("ai", s.made > 0 && s.madeAi > 0, d);
  snprintf(d, sizeof d, "квадов с цветом не 0x202020: %d из %d (пример 0x%06x)", bad, n, badc); check("neutral", n > 0 && bad == 0, d);
  printf("RESULT %s провалов %d\n", fails ? "FAIL" : "PASS", fails);
  (void)amax; return fails ? 1 : 0;
}
