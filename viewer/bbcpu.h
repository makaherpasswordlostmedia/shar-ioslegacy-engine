// Правка 410, шаг 0 плана ME (docs/handoff/ME_ПЛАН_2026-10-09.md, раздел 4): доля процессора потока за секунду для строки BBCPU (main.c
// bbProbeThreadsSecond). Было: при смене уровня sndShutdown/sndInit пересоздают audio_mix/audio_io с теми же именами, зонд держит
// старую базу bbThRun, у нового потока runClocks меньше — разность unsigned long long уходит в минус и даёт T3 smoke.txt:5024
// «pct=44/0/815353985/815354014/0». Теперь: run < базы — поток новый, база сбрасывается, доля за эту секунду 0 (событие 1);
// доля больше 100 — срез до 100 (событие 2). События считаются отдельно (BBCPU «bad=»), без среза в счётчике (поправка О3).
// BBCPU_OLD=1 — прежний расчёт (красный контроль tests/me/bbcpu_host.c). Без вызовов системы: тот же текст на PSP и на Маке
#ifndef BBCPU_H
#define BBCPU_H
#ifndef BBCPU_OLD
#define BBCPU_OLD 0
#endif
static inline unsigned bbPctStep(unsigned long long *base, unsigned long long run, unsigned dt, unsigned *ev) {
#if BBCPU_OLD
  (void)ev;
  unsigned p = *base && dt ? (unsigned)((run - *base) * 100ull / dt) : 0; *base = run; return p;
#else
  if (run < *base) { *base = run; if (ev) *ev |= 1u; return 0; }
  unsigned long long d = *base && dt ? (run - *base) * 100ull / dt : 0; *base = run;
  if (d > 100) { if (ev) *ev |= 2u; d = 100; }
  return (unsigned)d;
#endif
}
#endif
