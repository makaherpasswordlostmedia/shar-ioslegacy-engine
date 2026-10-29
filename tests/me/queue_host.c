// Очередь Media Engine (облако 05.10, задача 6) — гейт без PSP и без данных игры: настоящие потоки на Маке/Linux.
// Поток «ME» исполняет ящики так же, как meGameTask (viewer/me_gametask.c): своё задание, затем хвост очереди (CLOSED → next →
// took → прицепленный → FIN), и только потом «свободен» (слово состояния ME, как svcBusy модуля). Поток звука шлёт задание раз в
// 11,6 мс (буфер 512 при 44,1 кГц) и ждёт ответа до 50 мс (audio.c meCollect), поток частиц — раз в 16,7 мс, ждёт до 20 мс
// (fx.c fxMeCollect). Отправка — общий код службы viewer/me/mebox.h meBoxSubmit (тот же, что в meprobe.c).
// Проверки:
//   N (нормальный ME, частицы 2–4 мс): ни одно задание звука не потеряно (ответ всегда пришёл) и не посчитано дважды; звук,
//     отданный главному процессору (ME занят), — не больше 2 % (без очереди — каждый раз, когда ME считал частицы);
//   H (ME завис на частицах через 1 с): звук теряет не больше одного задания (дальше meOff — главный), частицы выключаются по
//     тайм-ауту и забываются (meSvcForget), к зависшему заданию никто не цепляется дольше ME_CHAIN_MAX_US.
// Красный: -DME_CHAIN_OLD=1 (без очереди) — звук на главном > 8 % в N.
//   cc -std=c11 -O2 -pthread -I viewer tests/me/queue_host.c -o queue && ./queue      (tests/me/queue.sh — красный + зелёный)
#define _GNU_SOURCE
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "me/mebox.h"

static MeBox boxS __attribute__((aligned(64))), boxF __attribute__((aligned(64)));
static MeQueue Q;
static atomic_int meBusy, meQuit, hangAt;          // hangAt: мс от старта, когда ME зависает на частицах (0 — никогда)
static _Atomic(volatile MeBox *) pend;
static atomic_uint doneS[4096];                     // сколько раз ME посчитал задание звука с этим номером
static unsigned t0;
static unsigned nowUs(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (unsigned)(ts.tv_sec * 1000000ull + ts.tv_nsec / 1000) - t0; }
static void waitUs(unsigned us) { usleep(us ? us : 1); }
static void spinUs(unsigned us) { unsigned e = nowUs() + us; while ((int)(nowUs() - e) < 0) {} }
static volatile MeBox *boxOf(unsigned n) {          // next/took хранят 32 бита адреса (как на PSP); на 64-битном хосте — по таблице
  if (n == (unsigned)(unsigned long)&boxS) return &boxS;
  if (n == (unsigned)(unsigned long)&boxF) return &boxF;
  return 0;
}
static void work(volatile MeBox *b) {               // «задание»: звук ~0,3 мс, частицы 2–4 мс; ME завис — частицы не кончаются
  if (b == &boxF) {
    int h = atomic_load(&hangAt);
    if (h && nowUs() / 1000 >= (unsigned)h) { while (!atomic_load(&meQuit)) usleep(1000); return; }
    spinUs(2000 + rand() % 2000);
  } else { spinUs(300); unsigned s = b->sent & 4095; atomic_fetch_add(&doneS[s], 1); }
  b->sum = 0; meSync(); b->done = b->sent; meSync();
}
static void *meThread(void *a) {
  (void)a;
  while (!atomic_load(&meQuit)) {
    volatile MeBox *b = atomic_exchange(&pend, (volatile MeBox *)0);
    if (!b) { usleep(50); continue; }
    work(b); if (atomic_load(&meQuit)) break;
    if (!ME_CHAIN_OLD) { unsigned n = meChainClose(b); if (n) { meChainTake(b, n); volatile MeBox *nb = boxOf(n); if (nb) work(nb); } meChainFinish(b); }
    atomic_store(&meBusy, 0);                       // слово состояния ME: вызов закончен (svcBusy модуля)
  }
  return 0;
}
static int kick(volatile MeBox *u) {
  int z = 0; if (!atomic_compare_exchange_strong(&meBusy, &z, 1)) return ME_SVC_BUSY;
  atomic_store(&pend, u); return (int)u->sent;
}

typedef struct { unsigned jobs, main, lost, off, maxWaitUs; } Stat;
static Stat sS, sF; static unsigned durMs;
static void *soundThread(void *a) {
  (void)a; unsigned next = nowUs();
  while (nowUs() / 1000 < durMs) {
    sS.jobs++;
    if (sS.off) sS.main++;
    else {
      int q = meBoxSubmit(&Q, 0, &boxS, ME_KIND_MIX, 0, 0, kick, nowUs, waitUs);
      if (q < 0) sS.main++;
      else { unsigned w0 = nowUs(); while (boxS.done != (unsigned)q && nowUs() - w0 < 50000) usleep(50);
        unsigned w = nowUs() - w0; if (w > sS.maxWaitUs) sS.maxWaitUs = w;
        if (boxS.done != (unsigned)q) { sS.lost++; sS.off = 1; } }   // audio.c meOff("timeout"): дальше звук на главном
    }
    next += 11610; while ((int)(nowUs() - next) < 0) usleep(200);
  }
  return 0;
}
static void *fxThread(void *a) {
  (void)a; unsigned next = nowUs();
  while (nowUs() / 1000 < durMs) {
    sF.jobs++;
    if (sF.off) sF.main++;
    else {
      int q = meBoxSubmit(&Q, 1, &boxF, ME_KIND_FX, 0, 0, kick, nowUs, waitUs);
      if (q < 0) sF.main++;
      else { unsigned w0 = nowUs(); while (boxF.done != (unsigned)q && nowUs() - w0 < 20000) usleep(50);
        if (boxF.done != (unsigned)q) { sF.lost++; sF.off = 1; Q.run[1] = 0; } }   // fx.c: off:timeout + meSvcForget(1)
    }
    next += 16667; while ((int)(nowUs() - next) < 0) usleep(200);
  }
  return 0;
}
static void run(unsigned ms, int hang) {
  memset(&boxS, 0, sizeof boxS); memset(&boxF, 0, sizeof boxF); memset(&Q, 0, sizeof Q); memset(&sS, 0, sizeof sS); memset(&sF, 0, sizeof sF);
  for (int i = 0; i < 4096; i++) atomic_store(&doneS[i], 0);
  atomic_store(&meBusy, 0); atomic_store(&meQuit, 0); atomic_store(&pend, (volatile MeBox *)0); atomic_store(&hangAt, hang);
  t0 = 0; t0 = nowUs(); durMs = ms;
  pthread_t m, s, f; pthread_create(&m, 0, meThread, 0); pthread_create(&s, 0, soundThread, 0); pthread_create(&f, 0, fxThread, 0);
  pthread_join(s, 0); pthread_join(f, 0); atomic_store(&meQuit, 1); pthread_join(m, 0);
}
static unsigned doubles(void) { unsigned d = 0; for (int i = 0; i < 4096; i++) if (atomic_load(&doneS[i]) > 1) d++; return d; }

int main(void) {
  srand(7); int fails = 0;
  run(4000, 0);
  unsigned dN = doubles();
  printf("N: звук %u заданий: на главном %u (%.1f %%), потеряно %u, дважды %u, прицеплено за частицами %u, ожидание до %.1f мс; "
         "частицы %u, на главном %u\n", sS.jobs, sS.main, 100.f * sS.main / sS.jobs, sS.lost, dN, Q.chained, sS.maxWaitUs / 1000.f, sF.jobs, sF.main);
  float pm = 100.f * sS.main / sS.jobs;
  printf("RESULT_N main_pct=%.2f lost=%u double=%u chained=%u\n", pm, sS.lost, dN, Q.chained);
  if (!ME_CHAIN_OLD) {
    if (sS.lost || dN) { printf("FAIL N: звук потерян или посчитан дважды\n"); fails++; }
    if (pm > 2.f) { printf("FAIL N: звук на главном %.1f %% > 2 %%\n", pm); fails++; }
    if (!Q.chained) { printf("FAIL N: ни одного прицепленного\n"); fails++; }
    run(3000, 1000);
    printf("H: ME завис на частицах с 1 с: звук потерял %u (выкл. %d), на главном %u из %u; частицы выкл. %d (тайм-аут %u)\n",
           sS.lost, sS.off, sS.main, sS.jobs, sF.off, sF.lost);
    if (sS.lost > 1) { printf("FAIL H: звук потерял %u заданий (> 1)\n", sS.lost); fails++; }
    if (!sF.off) { printf("FAIL H: частицы не выключились по тайм-ауту\n"); fails++; }
  }
  printf("RESULT %s\n", fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}
