// Пул клеток (№637, TEST23: отказ памяти у будки при 10 МБ свободно, самый большой кусок 2,3 МБ). Клетки города (десятки КБ) и их
// мелкие хвосты (ggBatch, сетка камеры) раньше шли прямо в malloc и дробили кучу: после MEMTRIM между ними застревали долгоживущие
// блоки, и крупное выделение (комната, карточка, машина миссии) не находило цельного куска. Теперь они складываются подряд в
// куски по CP_CHUNK, внутри кусков первый подходящий свободный блок со склейкой соседей (дыры от ушедших клеток переиспользуются новыми);
// кусок возвращается в кучу целиком, когда в нём не осталось живых блоков. Блок крупнее CP_DIRECT и отказ на новый кусок идут прямо в memalign, как раньше. CELLPOOL_OLD=1 — прежнее поведение.
// Замок malloc (рекурсивный) общий с загрузчиком: cpAlloc зовут загрузчик и главный поток, cpFree — главный.
#pragma once
// ВЫКЛЮЧЕН по умолчанию (замер эмулятора, тур 36 сцен с балластом 3 МБ: на L1 свободной кучи на 3 МБ меньше (4,4 против 7,0 МБ), цельный кусок не больше —
// дробит не клетки, а записи миссий art). Включить: -DCELLPOOL_ON=1
#ifndef CELLPOOL_ON
#define CELLPOOL_ON 0
#endif
#ifndef CELLPOOL_OLD
#define CELLPOOL_OLD (!CELLPOOL_ON)
#endif
#define CP_CHUNK (256u << 10)
#define CP_DIRECT (96u << 10)
#define CP_MAXCH 96
typedef struct { unsigned size, used, pad[14]; } CpHdr;   // 64 байта перед каждым блоком (строка кэша: заголовок не делит строку с данными, которые пишет чтение карты): размер вместе с заголовком, занят ли
typedef struct { unsigned char *base; unsigned live; } CpChunk;
static CpChunk cpCh[CP_MAXCH]; static int cpN; static unsigned cpAllocs, cpDirect, cpChunksMade, cpChunksFreed, cpChunkFail, cpLiveBytes;
extern void __malloc_lock(struct _reent *); extern void __malloc_unlock(struct _reent *);
static void *cpAlloc(size_t sz) {
  if (CELLPOOL_OLD || sz > CP_DIRECT) { cpDirect++; return memalign(16, sz ? sz : 16); }
  unsigned need = (((unsigned)sz + 63u) & ~63u) + 64u;
  __malloc_lock(_REENT);
  void *r = 0;
  for (int i = 0; i < cpN && !r; i++) { CpChunk *c = &cpCh[i]; if (!c->base) continue;
    for (unsigned o = 0; o < CP_CHUNK; ) { CpHdr *h = (CpHdr *)(c->base + o);
      if (!h->used && h->size >= need) {
        if (h->size - need >= 128u) { CpHdr *n = (CpHdr *)(c->base + o + need); n->size = h->size - need; n->used = 0; h->size = need; }
        h->used = 1; c->live++; cpLiveBytes += h->size; r = (unsigned char *)h + 64; break; }
      o += h->size; } }
  if (!r) {
    int k = -1; for (int i = 0; i < cpN; i++) if (!cpCh[i].base) { k = i; break; }
    if (k < 0 && cpN < CP_MAXCH) k = cpN++;
    unsigned char *b = k >= 0 ? memalign(64, CP_CHUNK) : 0;
    if (b) { cpCh[k].base = b; cpChunksMade++;
      CpHdr *h = (CpHdr *)b;
      if (CP_CHUNK - need >= 128u) { CpHdr *n = (CpHdr *)(b + need); n->size = CP_CHUNK - need; n->used = 0; h->size = need; } else h->size = CP_CHUNK;
      h->used = 1; cpCh[k].live = 1; cpLiveBytes += h->size; r = b + 64; }
    else cpChunkFail++;
  }
  __malloc_unlock(_REENT);
  if (!r) { cpDirect++; return memalign(16, sz ? sz : 16); }
  cpAllocs++; return r;
}
static void cpFree(void *p) {
  if (!p) return;
  if (!CELLPOOL_OLD) {
    __malloc_lock(_REENT);
    for (int i = 0; i < cpN; i++) { CpChunk *c = &cpCh[i];
      if (c->base && (unsigned char *)p >= c->base && (unsigned char *)p < c->base + CP_CHUNK) {
        CpHdr *h = (CpHdr *)((unsigned char *)p - 64); h->used = 0; cpLiveBytes -= h->size; c->live--;
        for (unsigned o = 0; o < CP_CHUNK; ) { CpHdr *a = (CpHdr *)(c->base + o);   // склейка соседних свободных
          if (!a->used) { unsigned e = o + a->size; while (e < CP_CHUNK && !((CpHdr *)(c->base + e))->used) { a->size += ((CpHdr *)(c->base + e))->size; e = o + a->size; } }
          o += a->size; }
        if (c->live == 0) { free(c->base); c->base = 0; cpChunksFreed++; }
        __malloc_unlock(_REENT); return; } }
    __malloc_unlock(_REENT);
  }
  free(p);
}
