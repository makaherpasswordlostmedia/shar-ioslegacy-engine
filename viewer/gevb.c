#include <pspkernel.h>
#include <pspgu.h>
#include "gevb.h"
// 16.10: кольцо по умолчанию ВЫКЛЮЧЕНО (самоаудит: выигрыша в эмуляторе нет, цена 128 КБ статической памяти; на железе не мерили). -DGEVB_ON=1 — включить
#ifndef GEVB_ON
#define GEVB_ON 0
#endif
#if GEVB_ON
#define GEVB_BYTES (128u << 10)
#else
#define GEVB_BYTES 64u   // кольца нет: память не занимается, geVbAlloc отдаёт sceGuGetMemory
#endif
static unsigned char ring[GEVB_BYTES] __attribute__((aligned(64)));
static unsigned used; static int active;
void geVbBegin(void) { used = 0; active = 1; }
void geVbEnd(void) {
  if (active && used) sceKernelDcacheWritebackRange(ring, (used + 63u) & ~63u);
  active = 0; used = 0;
}
void *geVbAlloc(unsigned bytes, int old) {
  unsigned n = (bytes + 15u) & ~15u;
  if (!GEVB_ON || old || !active || used + n > GEVB_BYTES) return sceGuGetMemory((int)bytes);
  void *p = ring + used; used += n; return p;
}
unsigned geVbUsed(void) { return used; }
