// Хост-гейт зазора по памяти для регионов впрок (viewer/regpre.h, regPreMemOk): куча у границы MEM_RESERVE + 4 МБ, регионы по 1,3 МБ сами меняют свободное.
// Модель: решение каждые 0,25 с (MEM_CHECK_US); свободное = база − (взято ? размер : 0). Считает включения за 60 с на разных базах (6,0…8,5 МБ) и размерах (0,6…2,5 МБ).
// old=1 — прежнее условие (красный: обязан давать > 2 включений за 10 с), old=0 — новое (зелёный: ≤ 2 за 10 с и регион остаётся взятым, пока памяти хватает по зазору).
#include <stdio.h>
#include "../../viewer/regpre.h"
#define MR (3u << 20)
static int run(int old, float baseMB, float regMB, int *rises) {
  unsigned lockT = 0, now = 1000; int was = 0, n = 0; unsigned t[400]; *rises = 0;
  for (int k = 0; k < 240; k++, now += 250000) {
    unsigned fr = (unsigned)((baseMB - (was ? regMB : 0.f)) * 1048576.f);
    int ok = regPreMemOk(fr, MR, was, now, &lockT, old);   // «вход разрешён» (ворота рядом — всегда да)
    if (ok && !was && n < 400) t[n++] = now;
    was = ok;
  }
  int worst = 0; for (int i = 0; i < n; i++) { int c = 0; for (int j = i; j < n && t[j] - t[i] < 10000000u; j++) c++; if (c > worst) worst = c; }
  *rises = n; return worst;
}
int main(void) {
  int wOld = 0, wNew = 0, tOld = 0, tNew = 0, held = 1;
  for (float b = 6.0f; b <= 8.51f; b += 0.1f) for (float r = 0.6f; r <= 2.51f; r += 0.1f) {
    int n; int w = run(1, b, r, &n); if (w > wOld) wOld = w; tOld += n;
    w = run(0, b, r, &n); if (w > wNew) wNew = w; tNew += n;
    // регион, уже взятый при свободном >= 4 МБ над резервом после загрузки (запас 1 МБ), не отдаётся
    unsigned lockT = 0; if (b - r >= 4.05f && !regPreMemOk((unsigned)((b - r) * 1048576.f), MR, 1, 5000, &lockT, 0)) held = 0;
  }
  // вынужденный выход: свободное < MEM_RESERVE + 1 МБ — регион отдан, повторный вход заперт на REGPRE_MEM_LOCK_S
  unsigned lk = 0; int out = regPreMemOk((unsigned)(3.5f * 1048576.f), MR, 1, 1000000, &lk, 0), in1 = regPreMemOk((unsigned)(9.f * 1048576.f), MR, 0, 2000000, &lk, 0), in2 = regPreMemOk((unsigned)(9.f * 1048576.f), MR, 0, 6000000, &lk, 0);
  int lockOk = !out && !in1 && in2;
  printf("REGPRE-память unit: прежнее: включений %d, максимум за 10 с %d; зазор: включений %d, максимум за 10 с %d; удержание %s, запрет повторного входа %s\n", tOld, wOld, tNew, wNew, held ? "да" : "НЕТ", lockOk ? "да" : "НЕТ");
  int ok = wOld > 2 && wNew <= 2 && held && lockOk;
  printf("REGPRE-ПАМЯТЬ-ЮНИТ: %s\n", ok ? "PASS (красный пойман, зелёный чист)" : "FAIL"); return ok ? 0 : 1;
}
