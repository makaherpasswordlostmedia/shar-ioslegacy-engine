// №538: решения очереди фонового чтения моделей машин миссии (viewer/main_render.h, mcrGet/mcrSync). Чистый C, без PSP: тест tests/mcr/pre_queue.c с имитацией задержки.
#ifndef MCRPRE_H
#define MCRPRE_H
enum { MCRPRE_TAKE, MCRPRE_DEFER, MCRPRE_WAIT };
#define MCRPRE_MAX_AGE 12   // вызовов mcrGet (≈ 2 за кадр), пока блок читается в фоне; дальше ждём остаток, как прежнее синхронное чтение
// Блок готов -> взять. Не готов: машина игрока (force) или ждали слишком долго -> дождаться остатка; иначе отложить (машина появится на следующем кадре)
static inline int mcrPreDecide(int ready, int age, int force) {
#ifdef PRE_BREAK   /* красный контроль теста: машина игрока откладывается как все */
  force = 0;
#endif
  if (ready) return MCRPRE_TAKE; if (force || age >= MCRPRE_MAX_AGE) return MCRPRE_WAIT; return MCRPRE_DEFER; }
// Начать фоновое чтение: есть свободное место в очереди и под модель, куча даёт запас (memPrefetchRoom), модели нет в памяти и чтение уже не идёт
static inline int mcrPreMayStart(int queueFree, int modelSlotsFree, int heapOk, int loaded, int pending) { return queueFree > 0 && modelSlotsFree > 0 && heapOk && !loaded && !pending; }
#endif
