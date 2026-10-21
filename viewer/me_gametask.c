// TEST 15 (04.10 вечер) — функция для Media Engine в памяти ИГРЫ (пользовательская память 0x088…), а не в модуле ядра sharme.prx.
// TEST 13–14 на железе: ячейка ставится только словом DMA из памяти игры (из памяти ядра — нет), а задание ME принимает
// (ME_STATE 0 → 1), но не заканчивает — ни строки в ящике. Версия: защита памяти PSP не пускает ME в память ядра модуля
// (0x0821…), где лежал наш meTask; у автора MIST (samples/poc-mist) задача — в памяти обычной программы. Здесь та же работа,
// что meWork в модуле (пустое задание и сумма буфера), без вызовов наружу, без $gp (ключи файла — viewer/CMakeLists.txt),
// выход — хвостом в обработчик ядра ME, как meSafeTaskMistFinish (адрес 0x883004c0, слово состояния -567).
#include "me/mebox.h"
#include "fpuguard.h"
#define MIX_DATA_FENCE(p) __asm__ volatile("cache 0x19, 0(%0)" : : "r"(p) : "memory")   // как в модуле: блок банка — мимо старого кэша ME
#include "mixdsp.h"
#include "fxdsp.h"
#include "citycull.h"
#include "me/mework.h"   // meWork — тот же текст, что в модуле: пустое задание, сумма, звук (mixDspRun), частицы (fxdRun из fxdsp.c игры)

// выход в обработчик ядра ME — отдельной функцией без кадра стека; meGameTask зовёт её хвостом (кадр уже снят), как модуль meSafeTaskMistFinish
int __attribute__((noinline)) meGameFinish(void) {
  __asm__ volatile(".set push\n\t.set noreorder\n\t.set noat\n\t"
                   "li $t0, 0xbfc00700\n\tli $t1, -567\n\tjr %0\n\tsw $t1, 0($t0)\n\t.set pop"
                   : : "r"(0x883004c0u) : "$t0", "$t1", "memory");
  return 0;
}

int meGameTask(int index, void *param) {
  (void)index;
  if (param) {
    unsigned a = (unsigned)param, cached = (a >> 29) == 4u || (a >> 29) == 0u;
    if (cached) __asm__ volatile("cache 0x19, 0(%0)\n\tsync" : : "r"(a) : "memory");
    meWork((volatile MeBox *)param);
    if (!cached && !ME_CHAIN_OLD) {   // очередь: ящик некэшируемый (схема 0) — следом прицепленный главным (звук за частицами)
      volatile MeBox *b = (volatile MeBox *)param; unsigned n = meChainClose(b);
      if (n) { meChainTake(b, n); meWork((volatile MeBox *)n); }
      meChainFinish(b);
    }
    if (cached) __asm__ volatile("cache 0x1b, 0(%0)\n\tsync" : : "r"(a) : "memory");
  }
  return meGameFinish();
}
