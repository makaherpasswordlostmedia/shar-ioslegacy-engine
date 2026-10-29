// Гейт защиты от кэша карты ARK-4 (правки 252/259, viewer/msio.c) на Маке. Своя модель драйвера карты по описанию поведения
// ARK-4 mscache (knowledge/facts/psp-ark4-mscache.yaml; код ARK не используется): один общий кэш чтения по СМЕЩЕНИЮ внутри файла,
// без имени файла и без замка; сброс — на open, ioctl, write в диапазон. Два потока много раз читают два разных файла с одних и
// тех же смещений вперемешку (как загрузчик клеток и поток звука). Проверка: каждый прочитанный блок = байтам своего файла.
// Красный: -DMSIO_OLD (прямое чтение) -> чужие байты; зелёный: viewer/msio.c -> 0 ошибок.
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
// --- подмена API PSP для msio.c
typedef int SceUID; typedef unsigned int SceSize;
static pthread_mutex_t semM = PTHREAD_MUTEX_INITIALIZER; static int semV = 1; static pthread_cond_t semC = PTHREAD_COND_INITIALIZER;
SceUID sceKernelCreateSema(const char *n, int a, int i, int m, void *o) { semV = i; return 1; }
int sceKernelPollSema(SceUID s, int n) { pthread_mutex_lock(&semM); int ok = semV >= n; if (ok) semV -= n; pthread_mutex_unlock(&semM); return ok ? 0 : -1; }
int sceKernelWaitSema(SceUID s, int n, void *t) { pthread_mutex_lock(&semM); while (semV < n) pthread_cond_wait(&semC, &semM); semV -= n; pthread_mutex_unlock(&semM); return 0; }
int sceKernelSignalSema(SceUID s, int n) { pthread_mutex_lock(&semM); semV += n; pthread_cond_broadcast(&semC); pthread_mutex_unlock(&semM); return 0; }
unsigned sceKernelGetSystemTimeLow(void) { return 0; }
int sceKernelGetThreadId(void) { static __thread int id; static int next = 1; if (!id) id = __sync_fetch_and_add(&next, 1); return id; }   // №741: владелец замка
// --- модель карты: два файла по 256 КБ, у каждого свой узор; общий кэш 32 КБ по смещению (как описано у ARK)
#define FSZ (256 * 1024)
static unsigned char file[2][FSZ]; static long fpos[2];
static unsigned char cbuf[32 * 1024]; static long cpos = -1; static int clen;
static void slow(void) { for (volatile int i = 0; i < 200; i++) ; sched_yield(); }
int sceIoRead(SceUID fd, void *data, SceSize len) {
  long pos = fpos[fd], cp = cpos; int cl = clen;   // снимок общего состояния (у ARK замка нет — модель тоже без замка, но без падения)
  if (cp >= 0 && cl > 0 && cl <= (int)sizeof cbuf && pos >= cp && pos + (long)len <= cp + cl) { slow(); memcpy(data, cbuf + (pos - cp), len); fpos[fd] = pos + len; return (int)len; }   // попадание — по смещению, файл не сверяется
  if (len <= sizeof cbuf) {
    cpos = -1; int n = (int)sizeof cbuf; if (pos + n > FSZ) n = (int)(FSZ - pos);
    for (int i = 0; i < n; i++) { cbuf[i] = file[fd][pos + i]; if ((i & 1023) == 0) slow(); }   // заполнение кэша не мгновенное
    cpos = pos; clen = n; memcpy(data, cbuf, len); fpos[fd] = pos + len; return (int)len;
  }
  memcpy(data, file[fd] + pos, len); fpos[fd] = pos + len; return (int)len;
}
int sceIoWrite(SceUID fd, const void *d, SceSize len) { cpos = -1; return (int)len; }
int sceIoIoctl(SceUID fd, unsigned cmd, void *a, int b, void *c, int e) { cpos = -1; return -1; }   // обработчик ARK: сброс, потом ошибка драйвера
int sceIoLseek32(SceUID fd, int off, int wh) { fpos[fd] = off; return off; }
#define MSIO_HOST_STUBS
#include "../../viewer/msio.c"
static volatile int bad, total;
static void *worker(void *p) {
  int fd = (int)(long)p; unsigned char buf[4096];
  for (int it = 0; it < 4000; it++) {
    long off = (long)((it * 4096L) % (FSZ - 4096));
    fpos[fd] = off;
#ifdef MSIO_OLD
    int r = sceIoRead(fd, buf, sizeof buf);
#else
    int r = msioRead(fd, buf, sizeof buf);
#endif
    total++;
    if (r != (int)sizeof buf || memcmp(buf, file[fd] + off, sizeof buf)) bad++;
  }
  return 0;
}
// №741: кадр экрана загрузки внутри чтения пишет журнал (msioWrite) — прежний замок ждал сам себя; сторож 2 с ловит зависание
static int pumpRead(int fd, void *d, unsigned n) { char log_[8] = "bb"; msioWrite(0, log_, 2); return sceIoRead(fd, d, n); }
static volatile int nestDone;
static void *nestWorker(void *p) { unsigned char buf[4096]; fpos[0] = 0; msioReadWait = pumpRead; int r = msioRead(0, buf, sizeof buf); msioReadWait = 0; nestDone = r == (int)sizeof buf ? 1 : 2; return 0; }
static int nestCase(void) {
  pthread_t t; pthread_create(&t, 0, nestWorker, 0);
  for (int i = 0; i < 200 && !nestDone; i++) usleep(10000);
  if (!nestDone) { printf("вложенная запись из чтения: ЗАВИСЛО (самоблокировка замка)\n"); return 1; }
  pthread_join(t, 0); printf("вложенная запись из чтения: прошло\n"); return nestDone == 1 ? 0 : 1;
}
int main(int argc, char **argv) {
  if (argc > 1 && !strcmp(argv[1], "nest")) { msioInit(); int r = nestCase(); printf("RESULT: %s\n", r ? "FAIL" : "OK"); fflush(stdout); _exit(r); }
  for (int f = 0; f < 2; f++) for (int i = 0; i < FSZ; i++) file[f][i] = (unsigned char)(f ? 0xA5 ^ (i * 7) : i * 13);
  msioInit();
  pthread_t a, b; pthread_create(&a, 0, worker, (void *)0L); pthread_create(&b, 0, worker, (void *)1L); pthread_join(a, 0); pthread_join(b, 0);
  printf("чтений %d, чужих или битых блоков %d\nRESULT: %s\n", total, bad, bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
