// Код, который исполняет Media Engine: одно задание из ящика (пустое, сумма буфера, звук, частицы). Один и тот же текст
// собирается в модуле ядра (viewer/me/sharme.c — старые ступени) и в игре (viewer/me_gametask.c — с 04.10 22:2x основной путь:
// TEST 13–16 на железе — ME не пускают в память ядра, код ME обязан лежать в памяти игры). Перед включением: mebox.h,
// ../fpuguard.h, MIX_DATA_FENCE, ../mixdsp.h, ../fxdsp.h. Без вызовов системы, без $gp, без чужих функций (ключи кода ME)
#pragma once
#include "../spatialdsp.h"
static void __attribute__((noinline)) meWork(volatile MeBox *b) {
  b->beat = b->beat + 1;
  unsigned st; __asm__ volatile("mfc0 %0, $12" : "=r"(st));
  b->status = st;
  unsigned fpu = st & (1u << 29), f0 = 0;
  if (fpu) { f0 = fpuGet(); b->fcsr0 = f0; fpuSet(f0 & FPU_KEEP_MASK); b->fcsr1 = fpuGet(); }   // ловушки FPU ME — выкл. на время задания
  else { b->fcsr0 = 0xffffffffu; b->fcsr1 = 0xffffffffu; }
  if (b->kind == ME_KIND_TINY) {        // TEST 10, лесенка: пустое задание — только ответ
    b->sum = 0x7e57u;
  } else if (b->kind == ME_KIND_FX) {   // правка 313: частицы и свечение (viewer/fxdsp.h); задание — в памяти игры, выровнено на 64
    unsigned j = b->job;
    if (b->words != sizeof(FxJob) || (j & 63u)) b->sum = ME_MIX_BADSIZE;
    else {
      for (unsigned a = j, e = j + sizeof(FxJob); a < e; a += 64)          // кэш ME над заданием — недействителен (главный его записал)
        __asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");
      __asm__ volatile("sync" : : : "memory");
      FxJob *J = (FxJob *)j;
      for (int r = 0; r < 4; r++) {                                        // таблицы пакета частиц: строки ME — недействительны
        unsigned a = J->inv[r][0] & ~63u, e = J->inv[r][0] + J->inv[r][1];
        if (J->inv[r][1]) for (; a < e; a += 64) __asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");
      }
      __asm__ volatile("sync" : : : "memory");
      unsigned cu = st & (1u << 29);                                       // счёт с плавающей точкой: сопроцессор FPU ME — включить
      if (!cu) __asm__ volatile("mtc0 %0, $12\n\tsync\n\tnop\n\tnop\n\tnop\n\tnop" : : "r"(st | (1u << 29)) : "memory");
      unsigned fs = fpuGet(); fpuSet(J->fcsr);                             // FCR31 — как у главного потока (округление, FS): бит в бит
      fxdRun(J);
      fpuSet(fs);
      if (!cu) __asm__ volatile("mtc0 %0, $12\n\tsync\n\tnop\n\tnop" : : "r"(st) : "memory");
      unsigned v = (unsigned)J->vout, ve = v + (unsigned)J->nq * 4u * sizeof(FxV);
      for (unsigned a = j, e = j + sizeof(FxJob); a < e; a += 64)          // итог — в память, кэш ME над заданием и вершинами пуст
        __asm__ volatile("cache 0x1b, 0(%0)" : : "r"(a) : "memory");
      for (unsigned a = v & ~63u; a < ve; a += 64) __asm__ volatile("cache 0x1b, 0(%0)" : : "r"(a) : "memory");
      __asm__ volatile("sync" : : : "memory");
      b->sum = 0;
    }
  } else if (b->kind == ME_KIND_CITY) { // №653: отсечение города (viewer/citycull.h); задание — в памяти игры, выровнено на 64, ниже 0x0A000000
    unsigned j = b->job;
    if (b->words != sizeof(CcJob) || (j & 63u)) b->sum = ME_MIX_BADSIZE;
    else {
      CcJob *J = (CcJob *)j;
      for (unsigned a = j, e = j + sizeof(CcJob); a < e; a += 64)          // кэш ME над заданием — недействителен (главный его записал)
        __asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");
      __asm__ volatile("sync" : : : "memory");
      for (int r = 0; r < 8; r++) {                                        // статика уровня и список PVS: строки ME — недействительны
        unsigned a = J->inv[r][0] & ~63u, e = J->inv[r][0] + J->inv[r][1];
        if (J->inv[r][1]) for (; a < e; a += 64) __asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");
      }
      __asm__ volatile("sync" : : : "memory");
      unsigned cu = st & (1u << 29);
      if (!cu) __asm__ volatile("mtc0 %0, $12\n\tsync\n\tnop\n\tnop\n\tnop\n\tnop" : : "r"(st | (1u << 29)) : "memory");
      unsigned fs = fpuGet(); fpuSet(J->fcsr);                             // FCR31 — как у главного потока: бит в бит
      J->magic = 0; int ok = ccRun(J);
      fpuSet(fs);
      if (!cu) __asm__ volatile("mtc0 %0, $12\n\tsync\n\tnop\n\tnop" : : "r"(st) : "memory");
      for (unsigned a = j, e = j + sizeof(CcJob); a < e; a += 64)          // итог — в память, кэш ME над заданием пуст
        __asm__ volatile("cache 0x1b, 0(%0)" : : "r"(a) : "memory");
      __asm__ volatile("sync" : : : "memory");
      b->sum = ok ? 0 : 1;
    }
  } else if (b->kind == ME_KIND_SPATIAL) {
    unsigned j=b->job;
    if(b->words!=sizeof(SpatialJob)||(j&63u))b->sum=ME_MIX_BADSIZE;
    else {
      for(unsigned a=j,e=j+sizeof(SpatialJob);a<e;a+=64)__asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");
      __asm__ volatile("sync" : : : "memory");
      mixSpatialBatchRun((SpatialJob *)j);
      for(unsigned a=j,e=j+sizeof(SpatialJob);a<e;a+=64)__asm__ volatile("cache 0x1b, 0(%0)" : : "r"(a) : "memory");
      __asm__ volatile("sync" : : : "memory");b->sum=0;
    }
  } else if (b->kind == ME_KIND_MIX) {  // правка 276: буфер звука (viewer/mixdsp.h); задание — в памяти игры, выровнено на 64
    unsigned j = b->job;
    if (b->words != sizeof(MixJob) || (j & 63u)) b->sum = ME_MIX_BADSIZE;   // модуль и игра из разных сборок — не считать
    else {
      for (unsigned a = j, e = j + sizeof(MixJob); a < e; a += 64)        // кэш ME над заданием — недействителен (главный его записал)
        __asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");
      __asm__ volatile("sync" : : : "memory");
      mixDspRun((MixJob *)j);
      for (unsigned a = j, e = j + sizeof(MixJob); a < e; a += 64)        // итог — в память, кэш ME над заданием пуст
        __asm__ volatile("cache 0x1b, 0(%0)" : : "r"(a) : "memory");      // (Hit Writeback Invalidate D)
      __asm__ volatile("sync" : : : "memory");
      b->sum = 0;
    }
  } else {
    const unsigned *p = (const unsigned *)b->buf; unsigned n = b->words;
    for (unsigned a = (unsigned)p & ~63u, e = (unsigned)(p + n); a < e; a += 64)   // строки кэша ME над буфером — недействительны
      __asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");                  // (Hit Invalidate D, hw-registers.h автора)
    __asm__ volatile("sync" : : : "memory");
    b->sum = meJobSum(p, n);
    for (unsigned a = (unsigned)p & ~63u, e = (unsigned)(p + n); a < e; a += 64)   // и после: в кэше ME ни строки буфера (игра потом
      __asm__ volatile("cache 0x19, 0(%0)" : : "r"(a) : "memory");                  // отдаст эту память другим, например роликам)
    __asm__ volatile("sync" : : : "memory");
  }
  if (fpu) fpuSet(f0);                  // FCR31 ME — как было до задания (код прошивки на ME дальше видит свой регистр)
  b->done = b->sent;                    // последним: главный процессор ждёт именно его
  __asm__ volatile("sync" : : : "memory");
}
