// Очередь Media Engine с приоритетом звука (облако 05.10, задача 6): договор «прицепить звук за частицами» (viewer/me/mebox.h
// meChainAttach / meChainClose / meChainTake / meChainFinish). ME и главный процессор работают одновременно, поэтому проверяем ВСЕ
// порядки: k шагов ME до вызова, j шагов ME сразу после записи next (на её sync), остальное ME делает, пока главный ждёт
// (wait) или после. Шаги ME: 0 — считает частицы (done); 1 — CLOSED и читает next; 2 — берёт (took); 3 — FIN.
// Итог каждого порядка — ровно одно из двух: звук посчитал ME (взял этот ящик один раз) или главный получил «не прицеплено»,
// и ME ящик не брал. Ни потери, ни двойного счёта. Красный: -DCHAIN_NAIVE=1 (главный смотрит только «сделано» частиц) — падает.
#include <stdio.h>
#include <string.h>
static void hook(void);
#define ME_SYNC_HOOK hook
#include "me/mebox.h"
static int fails;

typedef struct { volatile MeBox *b; int st; unsigned n; int tookSound; } Me;
static Me M; static volatile MeBox *SND; static int inMe, syncN, J;
static void meStep(void) {
  inMe = 1;
  if (M.st == 0) { M.b->done = M.b->sent; M.st = 1; }
  else if (M.st == 1) { M.n = meChainClose(M.b); M.st = 2; }
  else if (M.st == 2) { if (M.n) { meChainTake(M.b, M.n); if (M.n == (unsigned)(unsigned long)SND) M.tookSound++; } M.st = 3; }
  else if (M.st == 3) { meChainFinish(M.b); M.st = 4; }
  inMe = 0;
}
static void hook(void) { if (inMe) return; if (syncN++ == 0) for (int i = 0; i < J; i++) meStep(); }   // первый sync главного — после next
static void waitStep(unsigned us) { (void)us; meStep(); }

#if CHAIN_NAIVE
static int attach(volatile MeBox *run, volatile MeBox *a) {   // наивно: «частицы ещё не сделаны — прицеплю»
  if (run->done == run->sent) return 0;
  meSync();                                                    // (здесь ME может успеть сделать шаги)
  run->next = (unsigned)(unsigned long)a; return 1;
}
#else
static int attach(volatile MeBox *run, volatile MeBox *a) { return meChainAttach(run, a, waitStep); }
#endif

int main(void) {
  static MeBox fx __attribute__((aligned(64))), snd __attribute__((aligned(64)));
  int cases = 0;
  for (int k = 0; k <= 4; k++) for (int j = 0; j <= 4; j++) {
    memset(&fx, 0, sizeof fx); memset(&snd, 0, sizeof snd);
    fx.sent = 7; snd.sent = 3; snd.chain = ME_CH_CLOSED | ME_CH_FIN;
    M = (Me){&fx, 0, 0, 0}; SND = &snd; syncN = 0; J = j;
    for (int i = 0; i < k; i++) meStep();
    int r = attach(&fx, &snd);
    while (M.st < 4) meStep();                                 // ME доходит до конца сам
    int ok = (r == 1 && M.tookSound == 1) || (r == 0 && M.tookSound == 0);
    if (!ok) { printf("FAIL порядок k=%d j=%d: главный %s, ME взял звук %d раз\n", k, j, r ? "«прицеплено»" : "«нет»", M.tookSound); fails++; }
    cases++;
  }
  printf("RESULT %s: %d порядков шагов, провалов %d\n", fails ? "FAIL" : "PASS", cases, fails);
  return fails ? 1 : 0;
}
