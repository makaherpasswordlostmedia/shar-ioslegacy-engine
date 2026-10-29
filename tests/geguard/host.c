// Гейт проверки матриц (viewer/geguard.c, правки 259/252): конечная матрица проходит, NaN, бесконечность и мусор (|x| >= 2^24) —
// нет. Красный: сборка с -DGEGUARD_OLD (проверки нет) обязана упасть. Собирается на Маке: tests/geguard/run.sh
#define GEGUARD_HOST
#include "../../viewer/geguard.c"
#include <stdio.h>
#include <math.h>
static int fails;
static void t(const char *name, float bad, int want) {
  float m[16] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 20, 30, 1};
  m[5] = bad; int got = geMatOk(m, 16);
  if (got != want) { printf("  %s: geMatOk=%d, нужно %d\n", name, got, want); fails++; }
}
int main(void) {
  t("единичная", 1.f, 1); t("отрицательный ноль", -0.f, 1); t("1e6", 1e6f, 1); t("-1e6", -1e6f, 1); t("проекция 23.0", 23.f, 1);
  t("NaN", nanf(""), 0); t("+inf", INFINITY, 0); t("-inf", -INFINITY, 0); t("3e7", 3e7f, 0); t("-1e30", -1e30f, 0);
  printf(fails ? "FAIL %d\n" : "OK\n", fails); return fails != 0;
}
