/* psp_sys.c - kernel / io / thread / sema / time / display / power stubs on POSIX (iOS). */
#define _GNU_SOURCE
#include "psp_compat.h"
#include <pthread.h>
#include <semaphore.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <dirent.h>
#ifdef __APPLE__
#include <malloc/malloc.h>
#include <mach/mach_time.h>
#endif
void ge_invalidate_range(const void *p, unsigned n);

/* ---- time: clock_gettime exists only since iOS 10; this port targets iOS 7.0-9.3.5 -> mach_absolute_time / gettimeofday ---- */
static uint64_t mono_us(void) {
#ifdef __APPLE__
  static mach_timebase_info_data_t tb;
  if (!tb.denom) mach_timebase_info(&tb);
  return mach_absolute_time() * tb.numer / tb.denom / 1000u;
#else
  struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (uint64_t)t.tv_sec * 1000000u + t.tv_nsec / 1000;
#endif
}
static void real_ts(struct timespec *t) {
  struct timeval tv; gettimeofday(&tv, 0); t->tv_sec = tv.tv_sec; t->tv_nsec = (long)tv.tv_usec * 1000L;
}

/* ---- path mapping: ms0:/PSP/GAME/SHARVIEW/x -> <Documents>/SHARVIEW/x ---- */
static void mp(const char *in, char *out, size_t n) {
  const char *d = ios_docs_dir(); const char *p = in;
  if (!strncasecmp(p, "ms0:", 4) || !strncasecmp(p, "umd0:", 5) || !strncasecmp(p, "disc0:", 6)) p = strchr(p, ':') + 1;
  if (!strncasecmp(p, "/PSP/GAME/SHARVIEW", 18)) p += 18; else if (*in && strchr(in, ':')) { snprintf(out, n, "%s/ms0%s", d, p); return; }
  if (in[0] == '/' && !strchr(in, ':')) { snprintf(out, n, "%s", in); return; }
  snprintf(out, n, "%s/SHARVIEW%s%s", d, *p == '/' || !*p ? "" : "/", p);
}
SceUID sceIoOpen(const char *f, int fl, SceMode m) {
  char b[1024]; mp(f, b, sizeof b); int o = 0;
  o = (fl & 3) == 3 ? O_RDWR : (fl & 2) ? O_WRONLY : O_RDONLY; if (fl & PSP_O_CREAT) o |= O_CREAT; if (fl & PSP_O_TRUNC) o |= O_TRUNC; if (fl & PSP_O_APPEND) o |= O_APPEND; if (fl & PSP_O_EXCL) o |= O_EXCL;
  int fd = open(b, o, 0644); return fd < 0 ? (int)0x80010002 : fd; (void)m;
}
int sceIoClose(SceUID fd) { return close(fd); }
int sceIoRead(SceUID fd, void *d, SceSize n) { return (int)read(fd, d, n); }
int sceIoWrite(SceUID fd, const void *d, SceSize n) { return (int)write(fd, d, n); }
int sceIoLseek32(SceUID fd, int o, int w) { return (int)lseek(fd, o, w); }
SceOff sceIoLseek(SceUID fd, SceOff o, int w) { return lseek(fd, (off_t)o, w); }
int sceIoGetstat(const char *f, SceIoStat *s) { char b[1024]; struct stat st; mp(f, b, sizeof b); if (stat(b, &st)) return (int)0x80010002;
  memset(s, 0, sizeof *s); s->size = st.st_size; s->mode = S_ISDIR(st.st_mode) ? FIO_S_IFDIR : FIO_S_IFREG; return 0; }
int sceIoRemove(const char *f) { char b[1024]; mp(f, b, sizeof b); return unlink(b); }
int sceIoRename(const char *a, const char *c) { char x[1024], y[1024]; mp(a, x, sizeof x); mp(c, y, sizeof y); return rename(x, y); }
int sceIoMkdir(const char *d, SceMode m) { char b[1024]; mp(d, b, sizeof b); return mkdir(b, 0755); (void)m; }
SceUID sceIoDopen(const char *d) { char b[1024]; mp(d, b, sizeof b); DIR *x = opendir(b); return x ? (int)(intptr_t)x : (int)0x80010002; }
int sceIoDread(SceUID d, SceIoDirent *e) { struct dirent *r = readdir((DIR *)(intptr_t)d); if (!r) return 0; memset(e, 0, sizeof *e); strncpy(e->d_name, r->d_name, 255); e->d_stat.mode = r->d_type == DT_DIR ? FIO_S_IFDIR : FIO_S_IFREG; return 1; }
int sceIoDclose(SceUID d) { return closedir((DIR *)(intptr_t)d); }
static SceInt64 asyncRes[64];
int sceIoReadAsync(SceUID fd, void *d, SceSize n) { asyncRes[fd & 63] = read(fd, d, n); return 0; }
int sceIoWaitAsync(SceUID fd, SceInt64 *r) { *r = asyncRes[fd & 63]; return 0; }
int sceIoPollAsync(SceUID fd, SceInt64 *r) { *r = asyncRes[fd & 63]; return 0; }
int sceIoCancel(SceUID fd) { (void)fd; return 0; }
int sceIoIoctl(SceUID a, unsigned b, void *c, int d, void *e, int f) { (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return 0; }
int sceIoDevctl(const char *a, int b, void *c, int d, void *e, int f) { (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return (int)0x80010016; }

/* ---- threads / semas ---- */
typedef struct { pthread_t t; SceKernelThreadEntry fn; int started, done, id; char name[32]; } Th;
static Th ths[64]; static int nth = 1;
static void *tmain(void *a) { Th *t = a; t->fn(0, 0); t->done = 1; return 0; }
SceUID sceKernelCreateThread(const char *n, SceKernelThreadEntry e, int p, int s, unsigned at, void *o) { (void)p; (void)s; (void)at; (void)o; if (nth >= 64) return -1; Th *t = &ths[nth]; memset(t, 0, sizeof *t); t->fn = e; t->id = nth; strncpy(t->name, n, 31); return nth++; }
int sceKernelStartThread(SceUID id, SceSize al, void *ap) { Th *t = &ths[id]; (void)al; (void)ap; pthread_attr_t at; pthread_attr_init(&at); pthread_attr_setstacksize(&at, 512 * 1024);
  t->started = 1; return pthread_create(&t->t, &at, tmain, t); }
int sceKernelDeleteThread(SceUID id) { (void)id; return 0; }
int sceKernelTerminateDeleteThread(SceUID id) { (void)id; return 0; }
int sceKernelExitDeleteThread(int s) { pthread_exit((void *)(intptr_t)s); return 0; }
int sceKernelWaitThreadEnd(SceUID id, SceUInt *to) { (void)to; if (ths[id].started && !ths[id].done) pthread_join(ths[id].t, 0); return 0; }
int sceKernelGetThreadId(void) { return 0; } int sceKernelGetThreadCurrentPriority(void) { return 0x20; }
int sceKernelReferThreadStatus(SceUID id, SceKernelThreadInfo *i) { memset(i, 0, sizeof *i); strncpy(i->name, ths[id & 63].name, 31); i->status = ths[id & 63].done ? 0x10 : 0x2; return 0; }
int sceKernelReferThreadRunStatus(SceUID id, SceKernelThreadRunStatus *s) { (void)id; memset(s, 0, sizeof *s); return 0; }
int sceKernelGetThreadmanIdList(int t, SceUID *b, int n, int *c) { (void)t; (void)b; (void)n; *c = 0; return 0; }
int sceKernelRotateThreadReadyQueue(int p) { (void)p; sched_yield(); return 0; }
int sceKernelDelayThread(SceUInt us) { usleep(us); return 0; }
int sceKernelSleepThread(void) { for (;;) sleep(1000); } int sceKernelSleepThreadCB(void) { usleep(1000); return 0; }
typedef struct { pthread_mutex_t m; pthread_cond_t c; int n; int used; } Sm; static Sm sems[128];
SceUID sceKernelCreateSema(const char *n, unsigned a, int i, int m, void *o) { (void)n; (void)a; (void)m; (void)o; for (int k = 1; k < 128; k++) if (!sems[k].used) { sems[k].used = 1; sems[k].n = i; pthread_mutex_init(&sems[k].m, 0); pthread_cond_init(&sems[k].c, 0); return k; } return -1; }
int sceKernelDeleteSema(SceUID s) { sems[s & 127].used = 0; return 0; }
int sceKernelSignalSema(SceUID s, int n) { Sm *x = &sems[s & 127]; pthread_mutex_lock(&x->m); x->n += n; pthread_cond_broadcast(&x->c); pthread_mutex_unlock(&x->m); return 0; }
int sceKernelWaitSema(SceUID s, int n, SceUInt *to) { Sm *x = &sems[s & 127]; pthread_mutex_lock(&x->m);
  if (to) { struct timespec t; real_ts(&t); t.tv_nsec += (long)*to * 1000L; t.tv_sec += t.tv_nsec / 1000000000L; t.tv_nsec %= 1000000000L; while (x->n < n) if (pthread_cond_timedwait(&x->c, &x->m, &t)) { pthread_mutex_unlock(&x->m); return (int)0x800201a8; } }
  else while (x->n < n) pthread_cond_wait(&x->c, &x->m);
  x->n -= n; pthread_mutex_unlock(&x->m); return 0; }
int sceKernelPollSema(SceUID s, int n) { Sm *x = &sems[s & 127]; int r = 0; pthread_mutex_lock(&x->m); if (x->n >= n) x->n -= n; else r = (int)0x80020193; pthread_mutex_unlock(&x->m); return r; }
int sceKernelReferSemaStatus(SceUID s, SceKernelSemaInfo *i) { memset(i, 0, sizeof *i); i->currentCount = sems[s & 127].n; return 0; }
int sceKernelReferEventFlagStatus(SceUID e, SceKernelEventFlagInfo *i) { (void)e; memset(i, 0, sizeof *i); return 0; }
SceUID sceKernelCreateCallback(const char *n, SceKernelCallbackFunction f, void *a) { (void)n; (void)f; (void)a; return 1; }
int sceKernelRegisterExitCallback(SceUID c) { (void)c; return 0; }
void sceKernelExitGame(void) { ios_exit_requested(); for (;;) sleep(1000); }
unsigned sceKernelGetSystemTimeLow(void) { return (unsigned)mono_us(); }
SceInt64 sceKernelGetSystemTimeWide(void) { return (SceInt64)mono_us(); }
void sceKernelDcacheWritebackAll(void) {} void sceKernelDcacheWritebackInvalidateAll(void) {}
#undef sceKernelDcacheWritebackRange
void sceKernelDcacheWritebackRange(const void *p, unsigned n) { ge_invalidate_range(p, n); }
void sceKernelDcacheWritebackInvalidateRange(const void *p, unsigned n) { ge_invalidate_range(p, n); }
void sceKernelDcacheInvalidateRange(const void *p, unsigned n) { (void)p; (void)n; }
unsigned sceKernelMaxFreeMemSize(void) { return 48u << 20; } unsigned sceKernelTotalFreeMemSize(void) { return 64u << 20; }
int sceKernelVolatileMemTryLock(int u, void **p, int *s) { (void)u; *p = 0; *s = 0; return -1; } int sceKernelVolatileMemUnlock(int u) { (void)u; return 0; }
int sceKernelStartModule(SceUID m, SceSize a, void *p, int *s, void *o) { (void)m; (void)a; (void)p; (void)s; (void)o; return -1; }

/* ---- display / ge ---- */
static unsigned vcount; static uint8_t *edram;
static void vwait(void) { static unsigned long long last; unsigned long long now = mono_us(), per = 16667;
  if (last && now - last < per) usleep((unsigned)(per - (now - last))); last = mono_us(); vcount++; }
int sceDisplayWaitVblankStart(void) { vwait(); return 0; } int sceDisplayWaitVblank(void) { vwait(); return 0; } int sceDisplayIsVblank(void) { return 1; }
unsigned sceDisplayGetVcount(void) { return vcount; } unsigned sceDisplayGetCurrentHcount(void) { return vcount * 286; }
int sceDisplayGetFrameBuf(void **t, int *bw, int *pf, int s) { (void)s; if (t) *t = sceGeEdramGetAddr(); if (bw) *bw = 512; if (pf) *pf = 3; return 0; }
int sceDisplaySetMode(int m, int w, int h) { (void)m; (void)w; (void)h; return 0; } int sceDisplaySetFrameBuf(void *t, int b, int p, int s) { (void)t; (void)b; (void)p; (void)s; return 0; }
void *sceGeEdramGetAddr(void) { if (!edram) edram = (uint8_t *)calloc(1, 2u << 20); return edram; } unsigned sceGeEdramGetSize(void) { return 2u << 20; }

/* ---- ctrl ---- */
volatile unsigned ios_pad_buttons; volatile signed char ios_pad_lx, ios_pad_ly;
int sceCtrlSetSamplingCycle(int c) { (void)c; return 0; } int sceCtrlSetSamplingMode(int m) { (void)m; return 0; }
int sceCtrlPeekBufferPositive(SceCtrlData *p, int n) { for (int i = 0; i < n; i++) { memset(&p[i], 0, sizeof p[i]); p[i].TimeStamp = sceKernelGetSystemTimeLow(); p[i].Buttons = ios_pad_buttons; p[i].Lx = (unsigned char)(ios_pad_lx + 128); p[i].Ly = (unsigned char)(ios_pad_ly + 128); } return n; }
int sceCtrlReadBufferPositive(SceCtrlData *p, int n) { return sceCtrlPeekBufferPositive(p, n); }

/* ---- power / rtc / utility / debug ---- */
int scePowerSetClockFrequency(int a, int b, int c) { (void)a; (void)b; (void)c; return 0; } int scePowerTick(int t) { (void)t; return 0; } int scePowerRegisterCallback(int s, SceUID c) { (void)s; (void)c; return 0; }
int scePowerIsBatteryExist(void) { return 1; } int scePowerGetBatteryLifePercent(void) { return 100; } int scePowerGetCpuClockFrequency(void) { return 333; } int scePowerGetBusClockFrequency(void) { return 166; }
int sceRtcGetCurrentClockLocalTime(ScePspDateTime *t) { time_t n = time(0); struct tm l; localtime_r(&n, &l); t->year = l.tm_year + 1900; t->month = l.tm_mon + 1; t->day = l.tm_mday; t->hour = l.tm_hour; t->minute = l.tm_min; t->second = l.tm_sec; t->microsecond = 0; return 0; }
uint64_t sceRtcGetCurrentTick(uint64_t *t) { uint64_t v = (uint64_t)sceKernelGetSystemTimeWide(); if (t) *t = v; return v; }
int sceUtilityGetSystemParamInt(int id, int *v) { (void)id; *v = 1; return 0; } int sceUtilityLoadAvModule(int m) { (void)m; return 0; } int sceUtilityUnloadAvModule(int m) { (void)m; return 0; }
void pspDebugScreenInit(void) {} void pspDebugScreenInitEx(void *v, int p, int s) { (void)v; (void)p; (void)s; }
void pspDebugScreenPrintf(const char *f, ...) { va_list a; va_start(a, f); char b[512]; vsnprintf(b, sizeof b, f, a); va_end(a); ios_log("%s", b); }
void pspDebugScreenPuts(const char *s) { ios_log("%s", s); } void pspDebugScreenSetXY(int x, int y) { (void)x; (void)y; } void pspDebugScreenSetOffset(int o) { (void)o; }
void pspDebugScreenClear(void) {} void pspDebugScreenSetTextColor(u32 c) { (void)c; } void pspDebugScreenSetBackColor(u32 c) { (void)c; }
int sceKernelUtilsMt19937Init(void *c, unsigned s) { (void)c; srand(s); return 0; }

/* kernel-module loading is PSP-only */
int kuKernelCall(void *f, void *a) { (void)f; (void)a; return -1; } SceUID kuKernelLoadModule(const char *p, int f, void *o) { (void)p; (void)f; (void)o; return -1; }

/* newlib heap lock used by cellpool.h / smoke.h (heap walk): a plain recursive mutex here */
static pthread_mutex_t mlk; static pthread_once_t mlo = PTHREAD_ONCE_INIT;
static void mlinit(void) { pthread_mutexattr_t a; pthread_mutexattr_init(&a); pthread_mutexattr_settype(&a, PTHREAD_MUTEX_RECURSIVE); pthread_mutex_init(&mlk, &a); }
void __malloc_lock(struct _reent *r) { (void)r; pthread_once(&mlo, mlinit); pthread_mutex_lock(&mlk); }
void __malloc_unlock(struct _reent *r) { (void)r; pthread_mutex_unlock(&mlk); }

/* ---- mallinfo: iOS has none; report against a 96 MB budget (engine throttles streaming on low free heap) ---- */
struct mallinfo mallinfo(void) { struct mallinfo m; memset(&m, 0, sizeof m);
#ifdef __APPLE__
  malloc_statistics_t st; malloc_zone_statistics(NULL, &st); int used = (int)st.size_in_use; m.arena = (int)st.size_allocated; m.uordblks = used; m.fordblks = (96 << 20) - used;
#else
  m.arena = 32 << 20; m.fordblks = 32 << 20;
#endif
  return m; }

/* ---- savedata: DOCS/SAVEDATA/<game><save>/<file> ---- */
static int sdState;
static void sdPath(SceUtilitySavedataParam *p, char *dir, char *file) { snprintf(dir, 512, "%s/SAVEDATA/%s%s", ios_docs_dir(), p->gameName, p->saveName); snprintf(file, 640, "%s/%s", dir, p->fileName); }
int sceUtilitySavedataInitStart(SceUtilitySavedataParam *p) {
  char d[512], f[640], par[1024]; sdPath(p, d, f); int r = 0, m = (int)p->mode; snprintf(par, sizeof par, "%s/SAVEDATA", ios_docs_dir()); mkdir(par, 0755);
  if (m == PSP_UTILITY_SAVEDATA_AUTOSAVE || m == PSP_UTILITY_SAVEDATA_SAVE) { mkdir(d, 0755); FILE *x = fopen(f, "wb"); if (!x) r = (int)0x80110307; else { fwrite(p->dataBuf, 1, p->dataSize ? p->dataSize : p->dataBufSize, x); fclose(x); } }
  else if (m == PSP_UTILITY_SAVEDATA_AUTOLOAD || m == PSP_UTILITY_SAVEDATA_LOAD) { FILE *x = fopen(f, "rb"); if (!x) r = (int)0x80110306; else { size_t n = fread(p->dataBuf, 1, p->dataBufSize, x); fclose(x); p->dataSize = (unsigned)n; } }
  else if (m == SCE_UTILITY_SAVEDATA_AUTODELETE || m == PSP_UTILITY_SAVEDATA_DELETE || m == SCE_UTILITY_SAVEDATA_SINGLEDELETE) { if (unlink(f)) r = (int)0x80110306; rmdir(d); }
  p->base.result = r; sdState = 2; return 0;
}
int sceUtilitySavedataGetStatus(void) { return sdState; } int sceUtilitySavedataUpdate(int n) { (void)n; if (sdState == 2) sdState = 3; return 0; } int sceUtilitySavedataShutdownStart(void) { sdState = 0; return 0; }

/* linker --wrap shims (Apple ld has no --wrap): the wrappers in memwatch.c / main_stream.h are simply never called */
void *__real_malloc(size_t n) { return malloc(n); } void *__real_calloc(size_t a, size_t b) { return calloc(a, b); }
void *__real_realloc(void *p, size_t n) { return realloc(p, n); } void __real_free(void *p) { free(p); }
void *__real_memalign(size_t a, size_t n) { void *p = 0; if (a < sizeof(void *)) a = sizeof(void *); return posix_memalign(&p, a, n) ? 0 : p; }
int __real_sceIoClose(SceUID fd) { return sceIoClose(fd); }
