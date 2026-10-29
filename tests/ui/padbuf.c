// Правка Роба 25 (брифинг: Continue / Cancel с первого нажатия) — проверка на Маке чтения пульта viewer/padbuf.h.
// Пульт PSP даёт отсчёт каждую развёртку (60 Гц); кадр игры читает последние PADBUF_N. Подложенные входы:
//   1. короткое нажатие X (50 мс) целиком между двумя чтениями долгого кадра (120 мс: чтение картинки/музыки миссии) —
//      прежний способ (только последний отсчёт) его теряет (КРАСНОЕ), новый ловит один раз (ЗЕЛЁНОЕ);
//   2. то же для △ (Cancel) и нажатие в обычном кадре 33 мс;
//   3. нажатие во время загрузки ДО показа брифинга (since) — не считается; нажатие после показа — считается;
//   4. удержание кнопки несколько кадров — одно нажатие, не повтор;
//   5. эмулятор без меток времени (все 0) — как прежде по последнему отсчёту.
//   cc -O1 -I viewer tests/ui/padbuf.c -o build/padbuf-host && build/padbuf-host   (код 0 — всё зелёное)
//   build/padbuf-host --old  — прежний способ во всех случаях (обязан покраснеть: код 1)
#include <stdio.h>
#include <string.h>
#include "padbuf.h"

#define X 0x4000u
#define T 0x1000u
static int old;
// лента отсчётов: us — метка, b — кнопки; чтение в момент tRead берёт последние PADBUF_N отсчётов с меткой <= tRead
typedef struct { unsigned us[4096], b[4096]; int n; } Tape;
static void tape(Tape *t, unsigned t0, unsigned t1, unsigned down0, unsigned down1, unsigned btn, int zeroTs) {
  t->n = 0;
  for (unsigned us = t0; us <= t1 && t->n < 4096; us += 16667) {
    t->us[t->n] = zeroTs ? 0 : us; t->b[t->n] = (us >= down0 && us < down1) ? btn : 0; t->n++;
  }
}
static unsigned readAt(const Tape *t, unsigned tRead, PadEdges *e, unsigned *prevOld, unsigned since, int zeroTs) {
  int last = -1; for (int i = 0; i < t->n; i++) if ((zeroTs ? (unsigned)i * 16667u : t->us[i]) <= tRead) last = i;
  if (last < 0) return 0;
  int first = last - PADBUF_N + 1; if (first < 0) first = 0;
  if (old) return padEdgesLast(prevOld, t->b[last]);
  return padEdges(e, t->us + first, t->b + first, last - first + 1, since);
}
static int bad;
static void check(const char *what, int got, int want) {
  int ok = got == want; bad += !ok;
  printf("%-5s %s: нажатий %d (нужно %d)\n", ok ? "ok" : "FAIL", what, got, want);
}
static int presses(unsigned btn, unsigned frameUs, unsigned down0, unsigned down1, unsigned since, int zeroTs) {
  Tape t; tape(&t, 0, 2000000, down0, down1, btn, zeroTs);
  PadEdges e; memset(&e, 0, sizeof e); unsigned prevOld = 0; int n = 0;
  for (unsigned tr = 0; tr <= 2000000; tr += frameUs) if (readAt(&t, tr, &e, &prevOld, since, zeroTs) & btn) n++;
  return n;
}
int main(int argc, char **argv) {
  old = argc > 1 && !strcmp(argv[1], "--old");
  // 1: долгий кадр 120 мс, X нажат 50 мс между чтениями 720 и 840 мс
  check("X 50 мс между чтениями долгого кадра 120 мс", presses(X, 120000, 740000, 790000, 0, 0), 1);
  check("△ 50 мс между чтениями долгого кадра 120 мс", presses(T, 120000, 745000, 795000, 0, 0), 1);
  // 2: обычный кадр 33 мс
  check("X 90 мс, кадр 33 мс", presses(X, 33333, 500000, 590000, 0, 0), 1);
  // 3: нажатие во время загрузки до показа брифинга (показан на 1.0 с) — не считается; после — считается
  check("X во время загрузки до показа брифинга", presses(X, 120000, 900000, 950000, 1000000, 0), 0);
  check("X после показа брифинга", presses(X, 120000, 1100000, 1150000, 1000000, 0), 1);
  // 4: удержание 600 мс — одно нажатие
  check("X удержан 600 мс", presses(X, 33333, 300000, 900000, 0, 0), 1);
  // 5: эмулятор без меток: как прежде (длинное нажатие ловится, одно)
  check("без меток времени, X 200 мс", presses(X, 33333, 300000, 500000, 0, 1), 1);
  printf("пульт по отсчётам: %s\n", bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
