// Нажатия кнопок между кадрами (правка Роба 25, видео с PSP 3:37–3:50: «брифинг держится, пока жмёшь» — Continue / Cancel
// должны срабатывать с первого нажатия). Прежде кадр читал ОДИН последний отсчёт пульта (sceCtrlPeekBufferPositive(.., 1)):
// короткое нажатие, целиком уместившееся между двумя чтениями (долгий кадр: чтение музыки миссии и картинок, загрузка,
// переход), терялось. Пульт опрашивается каждую развёртку (sceCtrlSetSamplingCycle(0)) и хранит последние отсчёты с
// метками времени: кадр берёт все новые с прошлого чтения и собирает нажатия (фронты) по каждому.
// Чистый C без PSP — проверка на Маке tests/ui/padbuf.c (прежний способ на подложенном коротком нажатии — красный).
#ifndef SHAR_PADBUF_H
#define SHAR_PADBUF_H
#define PADBUF_N 16                                   // отсчётов за чтение: 16 развёрток ≈ 0.27 с
typedef struct { unsigned last, prev; int init; } PadEdges;
// ts, bt — метки времени отсчётов и кнопки, от старых к новым (n > 0). -> кнопки, нажатые с прошлого вызова.
// Отсчёты не новее прошлого — пропуск; метки не идут (эмулятор без меток) — фронт по последнему отсчёту, как прежде.
// since != 0 — метка отсчёта, когда на экране появился брифинг (main.c): нажатия раньше него не считаются (нажатое во время
// загрузки не пролистывает брифинг, которого игрок ещё не видел)
static inline unsigned padEdges(PadEdges *e, const unsigned *ts, const unsigned *bt, int n, unsigned since) {
  unsigned hit = 0; int fresh = 0;
  if (n <= 0) return 0;
  if (!e->init) { e->init = 1; e->last = ts[n - 1]; e->prev = bt[n - 1]; return 0; }
  for (int i = 0; i < n; i++) {
    if ((int)(ts[i] - e->last) <= 0) continue;
    unsigned h = bt[i] & ~e->prev;
    if (!since || (int)(ts[i] - since) > 0) hit |= h;
    e->prev = bt[i]; e->last = ts[i]; fresh = 1;
  }
  if (!fresh) { hit |= bt[n - 1] & ~e->prev; e->prev = bt[n - 1]; }
  return hit;
}
// прежний способ (только последний отсчёт) — для проверки tests/ui/padbuf.c
static inline unsigned padEdgesLast(unsigned *prev, unsigned b) { unsigned h = b & ~*prev; *prev = b; return h; }
#endif
