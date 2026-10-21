// Прыжок и двойной прыжок Гомера: порт (viewer/homer.c) против записи PS2 по ВЕРНОМУ адресу мирового корня.
//   tests/homer_jump/host.sh            (зелёный на новом коде; красный контроль: HOST_CFLAGS=-DHOMER_JUMP_PS2_OLD=1)
//
// Эталон PS2 (наблюдатель 09.10.2026 16:45, ~/Downloads/shar-psp-ps2-w/build/twins/o4/, только чтение):
//   ps2_homer_jump/trace.tsv        (рецепт tools/twins/recipes/ps2_homer_jump.json: X нажат кадр 20..26, стоя, дом m0d)
//     sha256 d536a3c78a652a5e0a8ada821f70be30833238bfeda68a437b3a5ca160cf637e
//   ps2_homer_double_jump/trace.tsv (то же + второй X кадр 36..42, т.е. через 0,32 с после первого)
//     sha256 e7ba01f2bb58c58b23d01b900dcb12f18e2efb4ad432393f1c6bffcc94fdb6d4
//   Корень Гомера — sim::SimState 0xa24570+0x40 = 0xa245b0/b4/b8 (факт ps2-r6-foot-death, native_binding);
//   старый 0xa24a70 (choreo::RootTransformController) в этих же записях расходится по y до 0,068 / 0,076 м.
//   Кадр записи = 1/50 с (PAL). Разбор: python3 -I tools/twins/homer_jump_ps2.py <trace.tsv> [кадр от, до]...
//   Одинарный: выборочная вершина 1,8345 м (кадр 40), парабола 1,8383 м, g 25,19; парабола пересекает землю на
//     кадрах 20,96 и 59,16 -> полёт от отрыва 0,764 с (у PS2 отрыв ~1 кадр после нажатия; у порта — в кадре нажатия).
//   Двойной: выборочная вершина 2,7062 м (кадр 52), парабола второго отрезка (кадры 38..74) 2,7121 м, g 24,81;
//     касание 74,45 -> полёт от отрыва (20,96) 1,070 с.
// Порт сидит в той же точке мира (x 221.872, z 177.005 — z отзеркален), шаг кадра PSP 1/60 и ровные 1/30.
// Допуски (от записи, не от порта): вершина — [выборочная − 0,005; парабола + 0,010] м; у двойного ещё ±0,032 м —
// момент второго X известен до кадра записи (0,02 с) при вертикальной скорости ~1,6 м/с в этот момент. Время полёта —
// ±0,04 с (выборка записи через 2 кадра, precision_vsync 2) и сверху ещё кадр порта (касание отмечается концом кадра).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "homer.h"

static ColWorld world; static int fails;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(16, (sz + 15) & ~15u);
  fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; }
  return m;
}
static void check(const char *what, float got, float lo, float hi, const char *expect) {
  int ok = got >= lo && got <= hi; if (!ok) fails++;
  printf("%-4s %-50s %8.4f   [%.4f .. %.4f]  (%s)\n", ok ? "ok" : "FAIL", what, got, lo, hi, expect);
}

#define PS2_X 221.872f
#define PS2_Z 177.005f   // запись: z -177.005 (мир оригинала), в порту z отзеркален

// один прогон: X на кадре 0; второй X (если t2 >= 0) — на кадре, ближайшем к t2 с. Возвращает вершину над землёй и
// время от первого нажатия до касания земли.
static void run(Homer *H, float dt, float t2, float *apex, float *tLand, int *jumps) {
  homerPlace(H, &world, PS2_X, 20.f, PS2_Z, 0.f);
  HomerInput in; memset(&in, 0, sizeof in);
  for (int i = 0; i < 60; i++) { homerUpdate(H, &world, NULL, &in, dt); homerPose(H); }   // встал на землю
  float y0 = H->y; H->maxY = H->y; *tLand = -1.f; *jumps = 0;
  int k2 = t2 >= 0.f ? (int)lrintf(t2 / dt) : -1, airborne = 0;
  for (int k = 0; k < (int)(3.f / dt); k++) {
    in.jump = (k == 0 || k == k2);
    homerUpdate(H, &world, NULL, &in, dt); homerPose(H);
    if (H->jumps > *jumps) *jumps = H->jumps;
    if (!H->grounded) airborne = 1;
    else if (airborne) { *tLand = (k + 1) * dt; break; }
  }
  *apex = H->maxY - y0;
}

int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr", *hom = argc > 2 ? argv[2] : "build/homer.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) { printf("no %s\n", lvl); return 1; }
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) { printf("bad level\n"); return 1; }
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned end = (unsigned)ftell(f);
  if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) { printf("COL1 failed\n"); return 1; }
  SkinModel *m = skinLoad(hom); if (!m) { printf("no %s\n", hom); return 1; }
  static Homer H; if (homerInit(&H, m)) { printf("homerInit: clips missing\n"); return 1; }
  printf("HOMER_JUMP_PS2_OLD=%d  HOMER_JUMP_H %.3f  HOMER_JUMP2_H %.3f  g %.2f\n",
         HOMER_JUMP_PS2_OLD, HOMER_JUMP_H, HOMER_JUMP2_H, HOMER_GRAVITY);

  const float dts[2] = {1.f / 60.f, 1.f / 30.f};
  for (int d = 0; d < 2; d++) {
    float dt = dts[d], apex, tl; int j; char w[96];
    run(&H, dt, -1.f, &apex, &tl, &j);
    printf("-- шаг 1/%.0f: одинарный\n", 1.f / dt);
    snprintf(w, sizeof w, "1/%.0f single jump: apex above ground, m", 1.f / dt);
    check(w, apex, 1.8345f - .005f, 1.8383f + .010f, "PS2 ps2_homer_jump: sampled 1.8345, parabola 1.8383");
    snprintf(w, sizeof w, "1/%.0f single jump: takeoff -> ground, s", 1.f / dt);
    check(w, tl, .764f - .04f, .764f + .04f + dt, "PS2 parabola: ground at frames 20.96 .. 59.16");
    run(&H, dt, .32f, &apex, &tl, &j);
    printf("-- шаг 1/%.0f: двойной (второй X через 0,32 с)\n", 1.f / dt);
    snprintf(w, sizeof w, "1/%.0f double jump: second jump fired", 1.f / dt);
    check(w, (float)j, 2.f, 2.f, "PS2: second rise after X at frame 36");
    snprintf(w, sizeof w, "1/%.0f double jump: apex above ground, m", 1.f / dt);
    check(w, apex, 2.7062f - .005f - .032f, 2.7121f + .010f + .032f, "PS2 ps2_homer_double_jump: sampled 2.7062, parabola 2.7121");
    snprintf(w, sizeof w, "1/%.0f double jump: takeoff -> ground, s", 1.f / dt);
    check(w, tl, 1.070f - .04f, 1.070f + .04f + dt, "PS2 parabola: takeoff 20.96, ground 74.45");
  }
  printf("%s: %d failed\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
