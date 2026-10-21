/* #385: keep the loading screen alive while a memory-stick read is pending.
   No render thread: GE and UI remain owned by the original main thread. */
#undef sceIoRead
#undef sceIoWrite
#ifndef LOAD_FUSE_HOST_STUBS
#include <pspkernel.h>
#include <pspiofilemgr.h>
#endif
#include <stdio.h>
#include "msio.h"
#include "load_fuse_io.h"
#ifndef LOAD_FUSE_ANIM_OLD
#define LOAD_FUSE_ANIM_OLD 0
#endif
/* №LOADWAIT: чтение через пульс кадров ждало конца sceIoPollAsync без тайм-аута (RESUME на железе: «фитиль не движется», PSP засыпает). Теперь: нет завершения за 3 с + 4 с на МБ ->
   строка в ящик (loadFuseIoNote), sceIoCancel, возврат позиции и синхронное чтение; если и оно вернёт ошибку — ошибка уходит вызывающему (экран ошибки загрузки, не вечное ожидание).
   LOAD_FUSE_WAIT_OLD=1 — прежнее. Тест: loadFuseIoHang(N) — первые N чтений «не завершаются» (flag loadreadhang N) */
#ifndef LOAD_FUSE_WAIT_OLD
#define LOAD_FUSE_WAIT_OLD 0
#endif
void (*loadFuseIoNote)(const char *);
static int hangN, waitOld = LOAD_FUSE_WAIT_OLD;
void loadFuseIoHang(int n) { hangN = n; }
static unsigned limitMs;
void loadFuseIoLimitMs(unsigned ms) { limitMs = ms; }   /* тест: порог ожидания чтения (по умолчанию 3 с + 4 с на МБ) */
void loadFuseIoWaitOld(int on) { waitOld = on != 0; }
static void (*pumpFrame)(void);
static SceUID owner = -1;
static int pumping, ownerPriority;
static unsigned slowUs, slowLeft;
int loadFuseIoPumping(void) { return pumping && sceKernelGetThreadId() == owner; }
int loadFuseIoProbe(void) { return slowUs != 0; }
void loadFuseIoSlow(unsigned us, unsigned chunks) { slowUs = us > 1000000u ? 1000000u : us; slowLeft = chunks; }
static int readWaiting(int fd, void *data, unsigned size) {
  if (!pumpFrame || sceKernelGetThreadId() != owner || pumping)
    return sceIoRead(fd, data, size);
  unsigned delay = slowLeft ? slowUs : 0; if (slowLeft) slowLeft--;
#if LOAD_FUSE_ANIM_OLD
  if (delay) sceKernelDelayThread(delay);
  return sceIoRead(fd, data, size);
#else
  /* A failed submission has not started a transfer: preserve the sync fallback. */
  int pos0 = sceIoLseek32(fd, 0, PSP_SEEK_CUR);
  int r = sceIoReadAsync(fd, data, size);
  if (r < 0) { if (delay) sceKernelDelayThread(delay); return sceIoRead(fd, data, size); }
  unsigned start = sceKernelGetSystemTimeLow();
  SceInt64 result = 0; int done = 0, hang = hangN > 0; if (hang) hangN--;
  unsigned limit = (unsigned)(3000000ull + (unsigned long long)size * 4000000ull / 1048576ull);   /* 3 с + 4 с на МБ */
  if (limitMs) limit = limitMs * 1000u;
  for (;;) {
    if (!waitOld && !done && sceKernelGetSystemTimeLow() - start > limit) {   /* не завершилось: отмена и синхронное чтение с той же позиции */
      char note[64]; snprintf(note, sizeof note, "read_%ums_size%u", (sceKernelGetSystemTimeLow() - start) / 1000u, size); if (loadFuseIoNote) loadFuseIoNote(note);
      sceIoCancel(fd); sceIoWaitAsync(fd, &result);
      sceIoLseek32(fd, (int)pos0, PSP_SEEK_SET);
      hang = 0; return sceIoRead(fd, data, size);
    }
    if (!done) {
      r = hang ? 1 : sceIoPollAsync(fd, &result);
      if (r < 0) { /* Drain before the caller can free the destination buffer. */
        int waited = sceIoWaitAsync(fd, &result);
        return waited < 0 ? waited : (int)result;
      }
      done = r == 0;
    }
    if (done && sceKernelGetSystemTimeLow() - start >= delay) break;
    pumping = 1; pumpFrame(); pumping = 0;
    /* Yield to the async I/O worker without adding a timer quantum per 64 KiB. */
    sceKernelRotateThreadReadyQueue(ownerPriority);
  }
  return (int)result;
#endif
}
void loadFuseIoBegin(void (*pump)(void)) {
  owner = sceKernelGetThreadId(); ownerPriority = sceKernelGetThreadCurrentPriority(); pumpFrame = pump; msioReadWait = readWaiting;
}
void loadFuseIoEnd(void) { msioReadWait = 0; pumpFrame = 0; owner = -1; pumping = 0; }
