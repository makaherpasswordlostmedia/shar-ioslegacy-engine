// №516 хост-тест: кривая «время -> масштаб по высоте» строки задания (viewer/ui_anim.h 2в) против замера PS2 и правила выхода «за один кадр».
//   cc -std=c11 -O2 -I viewer tests/ui/bubble_anim.c -lm -o build/tmp/bubble_anim && build/tmp/bubble_anim [ТАБЛИЦА.tsv] [--old]
// ТАБЛИЦА (по умолчанию tests/ui/bubble_anim_ps2.tsv): «t_с<TAB>масштаб»; допуск 0,03 по масштабу, 1 кадр 60 к/с (±1/60 с) по времени.
// КРАСНЫЙ: -DBUBBLE_ANIM_OLD=1 здесь не годится (кривая старая — UI_POP_BOX), его ловит сравнение 1: у старой кривой на t=0 масштаб 0,8 вместо 0,54 и
// выход идёт 0,2 с вместо одного кадра. python3-обёртка не нужна: код выхода 0 = PASS.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "ui_anim.h"
static int curveKind(void) { return BUBBLE_ANIM_OLD ? UI_POP_BOX : UI_POP_PILL; }
// №638: новая кривая против ширин рамки PS2 по кадрам 28..36 (50 к/с): 120 251 284 333 367 411 447 477 478 из 478 (ps2-bubble-open-anim.yaml); красный: -DBUBBLE_UNIFORM_OLD=1
static int uniformCheck(void) {
  static const int W[9] = {120, 251, 284, 333, 367, 411, 447, 477, 478}; int bad = 0; float sc, al;
  for (int i = 0; i < 9; i++) { uiPopState(UI_POP_PILL, 1, (i + .5f) / 50.f, &sc, &al); double e = fabs(sc - W[i] / 478.0); if (e > .06) { bad++; printf("FAIL кадр %d: PS2 %.2f код %.2f\n", 28 + i, W[i] / 478.0, sc); } }
  printf("%s единый масштаб рамки против ширин PS2 (9 кадров, допуск 0,06)\n", bad ? "FAIL" : "PASS");
  { int ok = 1; float p = 0; for (float t = 0; t < .3f; t += 1.f / 240.f) { uiPopState(UI_POP_PILL, 1, t, &sc, &al); if (sc + 1e-4f < p || sc < .2f || al < .25f || al > 1.0001f) ok = 0; p = sc; }
    uiPopState(UI_POP_PILL, 1, .2f, &sc, &al); if (sc < .999f || al < .999f) ok = 0; printf("%s вход не убывает, конец ровно 1, нет нулевой ширины и нулевой прозрачности\n", ok ? "PASS" : "FAIL"); bad += !ok; }
  { int alive = uiPopState(UI_POP_PILL, 0, 0.f, &sc, &al); printf("%s выход за один кадр\n", !alive ? "PASS" : "FAIL"); bad += alive; }
  return bad;
}
int main(int argc, char **argv) {
  if (!BUBBLE_UNIFORM_OLD) return uniformCheck() ? 1 : 0;
  const char *path = argc > 1 && argv[1][0] != '-' ? argv[1] : "tests/ui/bubble_anim_ps2.tsv"; int bad = 0;
  FILE *f = fopen(path, "r"); char ln[256]; int n = 0, nb = 0; double maxe = 0;
  if (!f) { printf("FAIL нет таблицы %s\n", path); return 1; }
  while (fgets(ln, sizeof ln, f)) {
    float t, w; if (ln[0] == '#' || sscanf(ln, "%f %f", &t, &w) != 2) continue;
    float sc, al; uiPopState(curveKind(), 1, t, &sc, &al);
    double e = fabs(sc - w); for (int d = -1; d <= 1; d += 2) { float s2; uiPopState(curveKind(), 1, t + d / 60.f, &s2, &al); if (fabs(s2 - w) < e) e = fabs(s2 - w); }
    n++; if (e > maxe) maxe = e; if (e > .03) { nb++; printf("FAIL t=%.3f таблица %.2f код %.2f\n", t, w, sc); }
  }
  fclose(f); printf("%s кривая против замера PS2: %d точек, расхождение макс %.3f\n", nb ? "FAIL" : "PASS", n, maxe); bad += nb;
  // прозрачность не меняется, ширина не трогается (масштаб только по высоте — ui.c ставит xf.sy)
  { float sc, al; int ok = 1; for (float t = 0; t < .3f; t += 1.f / 120.f) { uiPopState(curveKind(), 1, t, &sc, &al); if (al < .999f) ok = 0; }
    printf("%s заливка без проявления (прозрачность 1 с первого кадра)\n", ok ? "PASS" : "FAIL"); bad += !ok; }
  // выход: один кадр (на t=0 после снятия уже нечего рисовать)
  { float sc, al; int alive = uiPopState(curveKind(), 0, 0.f, &sc, &al), alive2 = uiPopState(curveKind(), 0, 1.f / 60.f, &sc, &al);
    int ok = !alive && !alive2; printf("%s выход за один кадр (без сжатия и затухания)\n", ok ? "PASS" : "FAIL"); bad += !ok; }
  // монотонность входа: масштаб не убывает, шаги по 1/30 с
  { float p = 0, sc, al; int ok = 1; for (float t = 0; t < .3f; t += 1.f / 240.f) { uiPopState(curveKind(), 1, t, &sc, &al); if (sc + 1e-4f < p) ok = 0; p = sc; } printf("%s вход не убывает\n", ok ? "PASS" : "FAIL"); bad += !ok; }
  return bad ? 1 : 0;
}
