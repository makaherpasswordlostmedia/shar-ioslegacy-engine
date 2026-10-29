// Ловушка вылета SHARVIEW (аудит ведущего 01.10 22:35, обрыв 22:26 на a95a30cd: ящик без STALL, встал весь процессор).
// Модуль ядра sharexc.prx рядом с EBOOT; main.c грузит его первым делом (kuKernelLoadModule ARK-4) и передаёт папку игры.
// Исключение процессора в любом потоке -> строка «CRASH …» в конец blackbox.txt (кольцо ящика пишется с нуля фиксированной
// длиной BB_FILE, хвост за ним не затирается) и в crash.txt: epc (адрес команды), ra, badvaddr (адрес ошибки), cause,
// база модуля SHARVIEW (EBOOT — PRX, адрес плавает) и смещения от неё, цепочка вызовов, поток. Дальше упавший поток
// спит: сторож bbdog через 5 с пишет «STALL» (как при зависании) — CRASH остаётся хвостом.
// Строка кода: tools/crash_addr.py build/crash/<папка> (psp-addr2line по ELF выпуска, build/crash/elf/<EBOOT>.elf)
#include <pspkernel.h>
#include <pspdebug.h>
#include <psploadcore.h>
#include <pspthreadman_kernel.h>
#include <string.h>
#include <stdarg.h>

PSP_MODULE_INFO("sharexc", 0x1006, 1, 0);
PSP_MAIN_THREAD_ATTR(0);

static char gDir[200];
static char gLine[640];
static volatile int gHit;

// своя мелкая запись строк: libc ядра без printf (pspDebugDumpException тянет vsnprintf — заглушка, экран не используем)
int vsnprintf(char *b, size_t n, const char *f, va_list a) { if (n) b[0] = 0; return 0; }
static char *ps(char *p, const char *s) { while (*s && p < gLine + sizeof gLine - 2) *p++ = *s++; *p = 0; return p; }
static char *px(char *p, unsigned v) { char t[9]; for (int i = 7; i >= 0; i--, v >>= 4) t[i] = "0123456789abcdef"[v & 15]; t[8] = 0; return ps(p, t); }
static char *pd(char *p, unsigned v) { char t[12]; int i = 11; t[i] = 0; do { t[--i] = (char)('0' + v % 10); v /= 10; } while (v); return ps(p, t + i); }

static void put(const char *name, int append) {
  char fn[256]; unsigned l = strlen(gDir); memcpy(fn, gDir, l); strcpy(fn + l, name);
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | (append ? PSP_O_APPEND : PSP_O_TRUNC), 0777);
  if (f >= 0) { sceIoWrite(f, gLine, strlen(gLine)); sceIoClose(f); }
}

static void onExc(PspDebugRegBlock *r) {
  if (!gHit++) {
    SceModule *m = sceKernelFindModuleByName("SHARVIEW");
    unsigned base = m ? m->text_addr : 0, sz = m ? m->text_size : 0;
    char tn[32] = "?"; SceKernelThreadInfo ti; memset(&ti, 0, sizeof ti); ti.size = sizeof ti;
    if (sceKernelReferThreadStatus(sceKernelGetThreadId(), &ti) >= 0) { strncpy(tn, ti.name, sizeof tn - 1); tn[sizeof tn - 1] = 0; }
    unsigned ec = (r->cause >> 2) & 31;
    char *p = ps(gLine, "\nCRASH exc="); p = pd(p, ec);
    p = ps(p, " epc="); p = px(p, r->epc); p = ps(p, " ra="); p = px(p, r->r[31]); p = ps(p, " badv="); p = px(p, r->badvaddr);
    p = ps(p, " cause="); p = px(p, r->cause); p = ps(p, " sp="); p = px(p, r->r[29]); p = ps(p, " base="); p = px(p, base);
    p = ps(p, " size="); p = px(p, sz); p = ps(p, " off_epc="); p = px(p, r->epc - base); p = ps(p, " off_ra="); p = px(p, r->r[31] - base);
    p = ps(p, " thread="); p = ps(p, tn); p = ps(p, " trace");
    PspDebugStackTrace tr[8]; int k = pspDebugGetStackTrace2(r, tr, 8);
    for (int i = 0; i < k; i++) { p = ps(p, " "); p = px(p, tr[i].call_addr - base); }
    ps(p, "\n");
    // экран — первым (запись на карту из исключения может не пройти): красный фон, строка CRASH — сфоткать (03.10, правка 252)
    pspDebugScreenInit(); pspDebugScreenSetBackColor(0xff0000a0); pspDebugScreenSetTextColor(0xffffffff); pspDebugScreenClear();
    pspDebugScreenPuts("SHARVIEW CRASH - PHOTO THIS SCREEN, THEN HOLD POWER\n"); pspDebugScreenPuts(gLine);
    put("blackbox.txt", 1); put("crash.txt", 0);
  }
  for (;;) sceKernelDelayThread(1000000);
}

int module_start(SceSize args, void *argp) {
  if (args > 0 && argp) { unsigned l = args < sizeof gDir ? args : sizeof gDir - 1; memcpy(gDir, argp, l); gDir[l] = 0; }
  pspDebugInstallErrorHandler(onExc);
  return 0;
}
int module_stop(SceSize args, void *argp) { return 0; }
