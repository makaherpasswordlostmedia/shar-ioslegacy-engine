// SHARBENCH — стенд для PSP (Роб 03.10: «бенчи, которые прогонишь именно на PSP: замерь, как можно использовать Media Engine и
// что ещё оптимизировать; то, что не проверить здесь, — отдельно»). Отдельная папка PSP/GAME/SHARBENCH, игру не трогает.
// Замеры (всё в bench.txt рядом с EBOOT и на экране):
//   1. железо: частоты, свободная память, крупнейший блок, батарея, прошивка
//   2. процессор: цикл плавающей точки, целочисленный цикл, копирование памяти (МБ/с)
//   3. карта памяти: чтение ../SHARVIEW/level.shr подряд (МБ/с) и вразброс по 4 КБ (мс на чтение) — как подгрузка города
//   4. GE: заливка экрана полупрозрачными прямоугольниками (мс на слой), кадр 5650 с дизерингом и без
//   5. дизеринг (правка 230): экран с плавной тенью — верх с дизерингом, низ без; 6 с смотреть глазами
//   6. окно сохранения (правка 238): системная утилита сохраняет в отдельный слот при запасе памяти 1, 2, 3, 4 МБ — код ответа
//      каждого (0 — сохранила), слот стенда потом удаляется
// Media Engine — ступень 0 плана docs/ME_ПЛАН_2026-10-03.md (нужен модуль ядра): здесь только отметка «модуля нет».
#include <pspkernel.h>
#include <pspdisplay.h>
#include <pspdebug.h>
#include <pspgu.h>
#include <pspgum.h>
#include <pspge.h>
#include <psprtc.h>
#include <psppower.h>
#include <pspctrl.h>
#include <psputility.h>
#include <pspsysmem.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <math.h>
#include "../viewer/audio.h"   // микшер игры как есть (AUDIO_HOST: без потоков и sceAudio, смешивание по вызову)

PSP_MODULE_INFO("SHARBENCH", 0, 1, 0);
PSP_MAIN_THREAD_ATTR(THREAD_ATTR_USER | THREAD_ATTR_VFPU);
PSP_HEAP_SIZE_KB(6144);   // своя куча мала: остальная память — пробе окна сохранения (п. 6)

#define BUF_W 512
#define SCR_W 480
#define SCR_H 272
#define TXT_FB (2 * BUF_W * SCR_H * 2)   // третий кадр — только текст (процессор пишет в VRAM; кадры GE эмулятор не смешивает с записью процессора)
static unsigned int __attribute__((aligned(16))) list[262144];
static char dir[256], rep[12288]; static int rn;

static void P(const char *fmt, ...) {
  va_list a; va_start(a, fmt); char s[256]; vsnprintf(s, sizeof s, fmt, a); va_end(a);
  int n = (int)strlen(s); if (rn + n < (int)sizeof rep - 1) { memcpy(rep + rn, s, (size_t)n); rn += n; rep[rn] = 0; }
  pspDebugScreenPrintf("%s", s);
}
static unsigned us(void) { return sceKernelGetSystemTimeLow(); }
static void save(void) {
  char fn[300]; snprintf(fn, sizeof fn, "%sbench.txt", dir);
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | PSP_O_TRUNC, 0777); if (f >= 0) { sceIoWrite(f, rep, (SceSize)rn); sceIoClose(f); }
}
static int exitCb(int a, int b, void *c) { (void)a; (void)b; (void)c; save(); sceKernelExitGame(); return 0; }
static int cbThread(SceSize a, void *b) { (void)a; (void)b; int id = sceKernelCreateCallback("exit", exitCb, NULL); sceKernelRegisterExitCallback(id); sceKernelSleepThreadCB(); return 0; }

// ---- 2. процессор
static volatile float sinkF; static volatile unsigned sinkI;
static void benchCpu(void) {
  unsigned t0 = us(); float a = 1.0001f, b = 0.9999f, c = 0.f;
  for (int i = 0; i < 4000000; i++) { c = c * a + b; if (c > 1e6f) c = 0.f; }
  sinkF = c; unsigned tf = us() - t0;
  t0 = us(); unsigned x = 12345u;
  for (int i = 0; i < 8000000; i++) x = x * 1664525u + 1013904223u;
  sinkI = x; unsigned ti = us() - t0;
  P("CPU   float 4M mul-add %u ms, int 8M lcg %u ms\n", tf / 1000, ti / 1000);
  const int MB = 2; char *s = memalign(64, MB << 20), *d = memalign(64, MB << 20);
  if (s && d) {
    memset(s, 1, MB << 20); t0 = us();
    for (int k = 0; k < 16; k++) memcpy(d, s, MB << 20);
    unsigned tm = us() - t0; P("MEM   memcpy %d MB x16: %u ms = %.1f MB/s\n", MB, tm / 1000, 16.f * MB / (tm / 1e6f));
  } else P("MEM   memcpy: no memory\n");
  free(s); free(d);
}

// ---- 3. карта памяти
static void benchMs(void) {
  char fn[300]; snprintf(fn, sizeof fn, "%s", dir);
  char *p = strstr(fn, "SHARBENCH"); if (p) strcpy(p, "SHARVIEW/level.shr"); else strcat(fn, "level.shr");
  SceUID f = sceIoOpen(fn, PSP_O_RDONLY, 0);
  if (f < 0) { P("MS    no %s (%08x), read not measured\n", fn, f); return; }
  int size = (int)sceIoLseek32(f, 0, PSP_SEEK_END); sceIoLseek32(f, 0, PSP_SEEK_SET);
  char *b = memalign(64, 65536); int tot = 0; unsigned t0 = us();
  while (b && tot < (16 << 20) && tot < size) { int r = sceIoRead(f, b, 65536); if (r <= 0) break; tot += r; }
  unsigned ts = us() - t0;
  P("MS    sequential %d KB: %u ms = %.2f MB/s\n", tot >> 10, ts / 1000, (tot / 1048576.f) / (ts / 1e6f));
  unsigned seed = 7, tr = 0, mx = 0; int n = 0;
  for (int k = 0; k < 100 && b && size > 65536; k++) {
    seed = seed * 1103515245u + 12345u; int off = (int)((seed >> 4) % (unsigned)(size - 4096)) & ~2047;
    unsigned t1 = us(); sceIoLseek32(f, off, PSP_SEEK_SET); sceIoRead(f, b, 4096); unsigned dt = us() - t1;
    tr += dt; if (dt > mx) mx = dt; n++;
  }
  if (n) P("MS    random 4 KB x%d: avg %.2f ms, worst %.2f ms\n", n, tr / 1000.f / n, mx / 1000.f);
  free(b); sceIoClose(f);
}

// в newlib PSP нет posix_memalign, а микшер в режиме AUDIO_HOST берёт память им
int posix_memalign(void **pp, size_t al, size_t n) { *pp = memalign(al, n); return *pp ? 0 : 12; }

// ---- 3б. звук: настоящий микшер игры (viewer/audio.c) на пакетах звука с карты — стоимость смешивания на PSP
// (ступень 1 плана ME: сколько процессора уйдёт с основного, если микшер переедет на Media Engine)
static void benchSound(void) {
  char ad[300]; snprintf(ad, sizeof ad, "%s", dir);
  char *p = strstr(ad, "SHARBENCH"); if (p) strcpy(p, "SHARVIEW/audio/"); else strcat(ad, "audio/");
  if (audioInit(ad) < 0) { P("SND   no sound packs in %s: %s\n", ad, audioError()); return; }
  static short out[2 * 512];
  int ids[24], n = 0, h[24];
  for (int id = 0; id < 4000 && n < 24; id++) if (audioTestResLoops(id)) ids[n++] = id;
  int mus = audioTrack("sunday_drive");
  P("SND   bank ok: %d looping sounds, music %s\n", n, mus >= 0 ? "sunday_drive" : "none");
  const int want[] = {0, 1, 8, 24}; const char *const nm[] = {"silence", "music", "music+8", "music+24"};
  for (int k = 0; k < 4; k++) {
    int nv = want[k] > 1 ? want[k] : 0; if (!n) nv = 0;   // петель в банке мало — одни и те же звуки занимают разные голоса
    if (k >= 1 && mus >= 0) audioMusic(mus, 0);
    for (int i = 0; i < nv; i++) h[i] = audioPlayBus(ids[i % n], 0.5f, 0, 1, AUDIO_BUS_SFX);
    for (int w = 0; w < 20; w++) audioHostMix(out, 512);   // разгон: голоса стартовали, кольцо музыки наполнено
    float mixSum = 0, mixMax = 0; unsigned tot = 0, totMax = 0; AudioStats as;
    for (int b = 0; b < 200; b++) {
      unsigned t0 = us(); audioHostMix(out, 512); unsigned dt = us() - t0;
      audioStats(&as); mixSum += as.mixUs; if (as.mixUs > mixMax) mixMax = as.mixUs;
      tot += dt; if (dt > totMax) totMax = dt;
    }
    audioStats(&as);
    P("SND   %-8s voices %2d: mix %.2f ms avg / %.2f worst per 11.6 ms (%.1f%% CPU), with card reads %.2f / %.2f ms\n", nm[k],
      as.voices, mixSum / 200 / 1000, mixMax / 1000, mixSum / 200 / 11610.f * 100, tot / 200.f / 1000, totMax / 1000.f);
    for (int i = 0; i < nv; i++) if (h[i] > 0) audioStop(h[i]);
    for (int w = 0; w < 10; w++) audioHostMix(out, 512);
  }
  audioMusic(-1, 0); for (int w = 0; w < 10; w++) audioHostMix(out, 512);
  audioShutdown();
}

// ---- 4–5. GE и дизеринг
typedef struct { unsigned color; short x, y, z; } V;
static void quad(int x0, int y0, int x1, int y1, unsigned c) {
  V *v = sceGuGetMemory(2 * sizeof(V)); v[0].color = c; v[0].x = (short)x0; v[0].y = (short)y0; v[0].z = 0;
  v[1].color = c; v[1].x = (short)x1; v[1].y = (short)y1; v[1].z = 0;
  sceGuDrawArray(GU_SPRITES, GU_COLOR_8888 | GU_VERTEX_16BIT | GU_TRANSFORM_2D, 2, 0, v);
}
static void benchGe(void) {
  for (int dith = 1; dith >= 0; dith--) {
    sceGuStart(GU_DIRECT, list);
    if (dith) sceGuEnable(GU_DITHER); else sceGuDisable(GU_DITHER);
    sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
    sceGuClearColor(0xff202020); sceGuClear(GU_COLOR_BUFFER_BIT);
    sceGuFinish(); sceGuSync(0, 0);
    unsigned t0 = us();
    sceGuStart(GU_DIRECT, list);
    for (int k = 0; k < 40; k++) quad(0, 0, SCR_W, SCR_H, 0x20000000u | (unsigned)(k * 6));
    sceGuFinish(); sceGuSync(0, 0);
    unsigned t = us() - t0;
    P("GE    40 full-screen alpha layers, dither %s: %.2f ms (%.3f ms per layer)\n", dith ? "ON " : "off", t / 1000.f, t / 40000.f);
  }
}
static void *ditherScreen(void *fb, void *fb0, void *fb1) {   // -> показанный кадр
  // верх: плавная тень с дизерингом, низ: та же без; как тень под машиной на картинке будки
  for (int frame = 0; frame < 6 * 60; frame++) {
    sceGuStart(GU_DIRECT, list);
    sceGuClearColor(0xff6a3a2a); sceGuClear(GU_COLOR_BUFFER_BIT);   // синий фон будки (ABGR)
    sceGuEnable(GU_BLEND); sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);
    for (int half = 0; half < 2; half++) {
      if (half == 0) sceGuEnable(GU_DITHER); else sceGuDisable(GU_DITHER);
      int y0 = half ? SCR_H / 2 + 8 : 24, y1 = half ? SCR_H - 8 : SCR_H / 2 - 8;
      for (int x = 40; x < SCR_W - 40; x += 2) {   // мягкая тень: альфа гладко от 0 до 0.7 и обратно
        float u = (x - 40) / (float)(SCR_W - 80); unsigned a = (unsigned)(180.f * sinf(u * 3.14159f));
        quad(x, y0, x + 2, y1, (a << 24) | 0x00101010u);
      }
    }
    sceGuFinish(); sceGuSync(0, 0);
    pspDebugScreenSetOffset((int)fb); pspDebugScreenSetXY(1, 1); pspDebugScreenPrintf("TOP: dither ON   (game now)");
    pspDebugScreenSetXY(1, 18); pspDebugScreenPrintf("BOTTOM: dither OFF (booth fix 230)");
    sceDisplayWaitVblankStart(); fb = sceGuSwapBuffers();
  }
  sceGuDisable(GU_DITHER);
  return fb == fb0 ? fb1 : fb0;
}

static void textScreen(void) {   // показать кадр текста и печатать в него
  pspDebugScreenSetOffset(TXT_FB); pspDebugScreenClear(); pspDebugScreenSetXY(0, 0);
  sceDisplaySetFrameBuf((void *)((unsigned)sceGeEdramGetAddr() + TXT_FB), BUF_W, PSP_DISPLAY_PIXEL_FORMAT_565, PSP_DISPLAY_SETBUF_NEXTFRAME);
}

// ---- 6. окно сохранения при разном запасе памяти
static int util(int mode, void *buf, unsigned bufSize, unsigned dataSize) {
  static SceUtilitySavedataParam p; memset(&p, 0, sizeof p);
  p.base.size = sizeof p;
  sceUtilityGetSystemParamInt(PSP_SYSTEMPARAM_ID_INT_LANGUAGE, &p.base.language);
  sceUtilityGetSystemParamInt(PSP_SYSTEMPARAM_ID_INT_UNKNOWN, &p.base.buttonSwap);
  p.base.graphicsThread = 0x11; p.base.accessThread = 0x13; p.base.fontThread = 0x12; p.base.soundThread = 0x10;
  p.mode = (PspUtilitySavedataMode)mode; p.overwrite = 1;
  strcpy(p.gameName, "SHARBENCH"); strcpy(p.saveName, "00"); strcpy(p.fileName, "DATA.BIN");
  p.dataBuf = buf; p.dataBufSize = bufSize; p.dataSize = dataSize;
  strcpy(p.sfoParam.title, "SHAR bench"); strcpy(p.sfoParam.savedataTitle, "bench slot (delete)"); strcpy(p.sfoParam.detail, "test");
  p.sfoParam.parentalLevel = 1;
  int r = sceUtilitySavedataInitStart(&p); if (r < 0) return r;
  int shut = 0, seen = 0;
  for (int k = 0; k < 60 * 20; k++) {
    int s = sceUtilitySavedataGetStatus(); if (s >= 1) seen = 1;
    if (s == 2) sceUtilitySavedataUpdate(1);
    else if (s == 3 && !shut) { sceUtilitySavedataShutdownStart(); shut = 1; }
    else if (s == 0 && (shut || seen)) return p.base.result;
    sceDisplayWaitVblankStart();
  }
  return -1;
}
static void benchSave(void) {
  static char data[1024] __attribute__((aligned(64))); memset(data, 0x5a, sizeof data);
  const int reserveK[] = {4096, 3072, 2048, 1024};   // от безопасного к тесному; строка в файл после каждого (зависание видно по обрыву)
  for (unsigned i = 0; i < sizeof reserveK / sizeof *reserveK; i++) {
    int freeB = (int)sceKernelMaxFreeMemSize(), fill = freeB - reserveK[i] * 1024; SceUID blk = -1;
    if (fill > 0) blk = sceKernelAllocPartitionMemory(2, "benchfill", PSP_SMEM_Low, (SceSize)fill, NULL);
    unsigned t0 = us(); int r = util(PSP_UTILITY_SAVEDATA_AUTOSAVE, data, sizeof data, sizeof data); unsigned t = us() - t0;
    P("SAVE  free left %d KB (was %d KB, bench holds %d KB): result %08x %s, %u ms\n", reserveK[i], freeB >> 10,
      blk >= 0 ? fill >> 10 : 0, (unsigned)r, r == 0 ? "SAVED" : "ERROR", t / 1000);
    if (blk >= 0) sceKernelFreePartitionMemory(blk);
    save();
  }
  int r = util(SCE_UTILITY_SAVEDATA_AUTODELETE, 0, 0, 0);
  P("SAVE  bench slot deleted: result %08x\n", (unsigned)r);
}

int main(int argc, char **argv) {
  int th = sceKernelCreateThread("cb", cbThread, 0x11, 0x2000, 0, 0); if (th >= 0) sceKernelStartThread(th, 0, 0);
  if (argc > 0 && argv[0]) { strncpy(dir, argv[0], sizeof dir - 1); char *sl = strrchr(dir, '/'); if (sl) sl[1] = 0; }
  scePowerSetClockFrequency(333, 333, 166);
  void *fbp0 = (void *)0, *fbp1 = (void *)(BUF_W * SCR_H * 2);
  sceGuInit(); sceGuStart(GU_DIRECT, list);
  sceGuDrawBuffer(GU_PSM_5650, fbp0, BUF_W); sceGuDispBuffer(SCR_W, SCR_H, fbp1, BUF_W);
  { static const ScePspIMatrix4 dith = {{-4, 0, -3, 1}, {2, -2, 3, -1}, {-3, 1, -4, 0}, {3, -1, 2, -2}}; sceGuSetDither(&dith); }   // как игра (viewer/main.c)
  sceGuOffset(2048 - SCR_W / 2, 2048 - SCR_H / 2); sceGuViewport(2048, 2048, SCR_W, SCR_H);
  sceGuScissor(0, 0, SCR_W, SCR_H); sceGuEnable(GU_SCISSOR_TEST); sceGuDisable(GU_DEPTH_TEST);
  sceGuFinish(); sceGuSync(0, 0); sceDisplayWaitVblankStart(); sceGuDisplay(GU_TRUE);
  pspDebugScreenInitEx(NULL, PSP_DISPLAY_PIXEL_FORMAT_565, 0); textScreen();
  ScePspDateTime dt; sceRtcGetCurrentClockLocalTime(&dt);
  P("SHARBENCH %04d-%02d-%02d %02d:%02d\n", dt.year, dt.month, dt.day, dt.hour, dt.minute);
  P("HW    CPU %d MHz, bus %d MHz, free %d KB, largest block %d KB, battery %d%%, firmware %08x\n",
    scePowerGetCpuClockFrequency(), scePowerGetBusClockFrequency(), (int)(sceKernelTotalFreeMemSize() >> 10),
    (int)(sceKernelMaxFreeMemSize() >> 10), scePowerIsBatteryExist() ? scePowerGetBatteryLifePercent() : -1, sceKernelDevkitVersion());
  save();
  benchCpu(); save();
  benchMs(); save();
  benchSound(); save();
  benchGe(); save();
  ditherScreen(fbp0, fbp0, fbp1);
  textScreen(); pspDebugScreenPrintf("%s", rep);
  benchSave(); save();
  P("ME    Media Engine probe: not built yet (step 0 of docs/ME_PLAN)\n");
  P("DONE  bench.txt saved. Press HOME to exit, then connect PSP to the Mac\n"); save();
  sceKernelSleepThread();
  return 0;
}
