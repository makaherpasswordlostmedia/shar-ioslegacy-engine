// №516 хост-тест: подсказка Барта (viewer/ui_anim.h 2г) — кривые входа и ухода против замера PS2 и правила «пропадает в один кадр».
//   cc -std=c11 -O2 -I viewer tests/ui/tut_anim.c -lm -o build/tmp/tut_anim && build/tmp/tut_anim [ТАБЛИЦА.tsv]
// ТАБЛИЦА (по умолчанию tests/ui/tut_anim_ps2.tsv): «in|out<TAB>t_с<TAB>масштаб»; допуск 0,06 по масштабу и один шаг (1/30 с) по времени: фаза шага
// записи не известна (в записи А первый кадр попал в середину шага). КРАСНЫЙ: «--instant» — прежнее поведение (TUT_ANIM_OLD=1: сразу целиком, без ухода)
// обязано падать (код 1).
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "ui_anim.h"
static int instant;
static float enterK(float t) { return instant ? 1.f : uiTutEnterScale(t); }
static int exitK(float t, float *k) { if (instant) { *k = 1.f; return 0; } return uiTutExitScale(t, k); }
int main(int argc, char **argv) {
  for (int i = 1; i < argc; i++) if (!strcmp(argv[i], "--instant")) instant = 1;
  const char *path = argc > 1 && argv[1][0] != '-' ? argv[1] : "tests/ui/tut_anim_ps2.tsv"; int bad = 0, n = 0;
  FILE *f = fopen(path, "r"); char ln[256], kind[8]; double maxe = 0;
  if (!f) { printf("FAIL нет таблицы %s\n", path); return 1; }
  while (fgets(ln, sizeof ln, f)) {
    float t, w; if (ln[0] == '#' || sscanf(ln, "%7s %f %f", kind, &t, &w) != 3) continue;
    int in = !strcmp(kind, "in"); double best = 9;
    for (int d = -1; d <= 1; d++) { float tt = t + d / 30.f, k; if (tt < 0.f) tt = 0.f;
      if (in) k = enterK(tt); else if (!exitK(tt, &k)) continue; double e = fabs(k - w); if (e < best) best = e; }
    n++; if (best > maxe) maxe = best; if (best > .06) { bad++; printf("FAIL %s t=%.3f таблица %.2f\n", kind, t, w); }
  }
  fclose(f); printf("%s кривые против замера PS2: %d точек, расхождение макс %.3f\n", bad ? "FAIL" : "PASS", n, maxe);
  { float k0 = enterK(0.f), k1 = enterK(.2f); int ok = k0 >= .5f && k0 <= .6f && k1 == 1.f; printf("%s вход: старт %.2f (0,5–0,6), к 0,2 с полный размер\n", ok ? "PASS" : "FAIL", k0); bad += !ok; }
  { float k, kg; int a = exitK(0.f, &k); int ok = a && k > .9f && k < .92f; float kl = 0; int last = exitK(3.5f / 30.f, &kl), gone = !exitK(4.2f / 30.f, &kg);
    ok = ok && last && kl >= .5f && gone; printf("%s выход: первый кадр %.2f, последний видимый ≥0,5 (%.2f), дальше пузыря нет (до нуля не сжимается)\n", ok ? "PASS" : "FAIL", k, kl); bad += !ok; }
  { float p = 0; int ok = 1; for (float t = 0; t < .3f; t += 1.f / 240.f) { float k = enterK(t); if (k + 1e-4f < p) ok = 0; p = k; } printf("%s вход не убывает\n", ok ? "PASS" : "FAIL"); bad += !ok; }
  return bad ? 1 : 0;
}
