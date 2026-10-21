// Media Engine, ступень 0 — проба (правки Роба 269/273/276). Модуль ядра sharme.prx рядом с EBOOT, как ловушка вылетов
// sharexc.prx (viewer/kexc): игра грузит его через kubridge ARK-4 (kuKernelLoadModule) только по флагу сценария «meprobe»
// (viewer/me/meprobe.c); в обычной игре модуль не грузится и ME не трогается.
//
// Что делает (вся проба — внутри module_start, синхронно, около 0,1 с):
//   1. Образ ядра ME по слову 0x88300018 (таблица адресов функций ядра ME: t2img — PSP Slim и новее, у Роба PSP-2000).
//   2. Метод MIST (github.com/mcidclan/psp-media-engine-safe-task, MIT, viewer/me/vendor): ME перезапускается с прежним
//      вектором сброса, в пустую ячейку 13 таблицы вызовов ядра ME через DMACPLUS пишется адрес нашей функции meTask.
//      Ядро ME прошивки не правится: её задания (кадры роликов sceJpeg, сон) идут как раньше (MIST.md автора).
//   3. 100 заданий «свёртка 64 КБ буфера» (viewer/me/mebox.h meJobSum): почтовый ящик в некэшируемой памяти игры
//      (адрес | 0x40000000, выровнен на 64), время туда-обратно — по часам главного процессора, сумма сверяется с подсчётом
//      на главном. Нет ответа за 50 мс — «ME timeout»: дальше заданий нет, память ящика не отдаётся (ME мог бы в неё писать).
//   4. Уборка: ячейка 13 снова пустая, слово состояния ME 0xbfc00700 — как до пробы. Модуль остаётся в памяти (если ME
//      застрял в нашем коде, код не должен исчезнуть из-под него).
// Шаги — строками в me.txt рядом с EBOOT (видно, докуда дошло, даже если PSP встала). Итог — в MeProbeRes игры.
// На ME выключаются ловушки FPU (viewer/fpuguard.h, урок 252: 0/0 с ловушкой вешает всю приставку) — только если у ME
// включён сопроцессор FPU (Status, бит 29; иначе сама команда cfc1 — исключение на ME).
// Своё поверх библиотеки (правило порта): ячейка пишется своей функцией meInject с ограниченным ожиданием DMA (у автора
// ожидание бесконечное при выключенных прерываниях — зависание всей PSP, если DMA не завершится).
// Правка 276 — режим службы (флаг-файл meaudio, meprobe.c meAudioBoot): шаги 1–3 те же, ячейка остаётся нашей; задание
// «буфер звука» (viewer/mixdsp.h mixDspRun — та же функция, что у игры) игра шлёт через meSvcKick, перед роликом и сном —
// meSvcQuiesce (флаг ответа ME прошивки снят, слово состояния ME — как до службы). Шаги — «MEA …» в me.txt.
// Проба и служба в одном запуске не совмещаются (проба перезапускает ME): при службе проба пишет «ME skip audio».
// Правка 313 — схема памяти (mebox.h ME_MEM, выбор по итогам TEST 10): ящик в памяти игры (0) или в памяти ядра модуля (1–3),
// задание звука в ядре с переносом туда и обратно (3); второй клиент службы — частицы и свечение (viewer/fxdsp.h fxdRun, ME_KIND_FX).
// Заданий на ME — не больше одного сразу: kick, пока прошлое (любого клиента) не вышло из ME, отвечает ME_SVC_BUSY — клиент считает сам.
#include <pspkernel.h>
#include <pspthreadman_kernel.h>
#include <string.h>
#include <me-safe-task/me-stask-kcall.h>
#include <me-safe-task/me-stask-mist.h>
#include <me-core-mapper/dmacplus.h>
#include "mebox.h"
#include "../fpuguard.h"
// правка 313: строку кэша ME под блоком VAG банка — недействительной перед чтением (банк читается кэшируемым адресом в схемах 1–3)
#define MIX_DATA_FENCE(p) __asm__ volatile("cache 0x19, 0(%0)" : : "r"(p) : "memory")
#include "../mixdsp.h"   // правка 276: смешивание звука — та же функция, что у игры на главном процессоре (viewer/audio.c)
#include "../citycull.h"
#include "../fxdsp.h"    // правка 313: частицы и свечение — та же функция, что у игры на главном процессоре (viewer/fx.c)

// правка 313: libm в модуле — тот же машинный код, что у игры (cosf, sinf, atan2f, fminf, __ieee754_expf из libm.a). Ветви
// переполнения __ieee754_expf зовут __math_oflowf/__math_uflowf — у libm они ставят errno (глобальная переменная, на ME нельзя);
// здесь — то же значение без errno (newlib math_errf.c: xflowf(sign, 0x1p97f / 0x1p-95f)). У частиц |x| < 42 — сюда не доходит
static float __attribute__((noinline)) meXflowf(unsigned sign, float y) { volatile float t = sign ? -y : y; return t * y; }
float __math_oflowf(unsigned sign) { return meXflowf(sign, 0x1p97f); }
float __math_uflowf(unsigned sign) { return meXflowf(sign, 0x1p-95f); }

PSP_MODULE_INFO("sharme", 0x1006, 1, 0);
PSP_MAIN_THREAD_ATTR(0);

// --- библиотека MIST в модуле ядра: вызов «в режиме ядра» — прямой (у автора — kubridge kuKernelCall или свой kcall.prx)
int kCall_2(FCall const f, const unsigned int seg) { sceKernelIcacheInvalidateAll(); return ((FCall)(seg | (unsigned)f))(); }
int kCall_3(FPCall const f, const unsigned int seg, void *const param) { sceKernelIcacheInvalidateAll(); return ((FPCall)(seg | (unsigned)f))(param); }
int meSafeTaskCall(FPCall const call, void *const param) { return kCall_3(call, CACHED_KERNEL_MASK, param); }

// =========================== код, который исполняет ME (без вызовов системы, без $gp, без чужих функций) ===========================
#include "mework.h"   // meWork — общий с игрой (viewer/me_gametask.c)
// вход ME из обработчика вызовов ядра ME (MIST): param — некэшируемый адрес ящика; выход — только через meSafeTaskMistFinish
// (хвостовой переход после снятия кадра стека — проверяет tests/me/run.py по дизассемблеру)
// TEST 10: ящик может прийти и кэшируемым адресом ядра (0x80000000–0x9fffffff, как счётчик в примере автора MIST): тогда строку
// ящика в кэше ME — недействительной до работы и записать в память после (Hit Invalidate D / Hit Writeback Invalidate D)
int meTask(int index, void *param) {
  if (param) {
    // TEST 14: кэшируемый адрес — и ядра (0x8…), и памяти игры (0x0…, как счётчик в примере автора MIST poc-mist)
    unsigned a = (unsigned)param, cached = (a >> 29) == 4u || (a >> 29) == 0u;
    if (cached) __asm__ volatile("cache 0x19, 0(%0)\n\tsync" : : "r"(a) : "memory");
    meWork((volatile MeBox *)param);
    if (cached) __asm__ volatile("cache 0x1b, 0(%0)\n\tsync" : : "r"(a) : "memory");
  }
  return meSafeTaskMistFinish();
}
// ================================================================================================================================

static char gDir[192], gLine[256];
static char *ps(char *p, const char *s) { while (*s && p < gLine + sizeof gLine - 2) *p++ = *s++; *p = 0; return p; }
static char *px(char *p, unsigned v) { char t[9]; for (int i = 7; i >= 0; i--, v >>= 4) t[i] = "0123456789abcdef"[v & 15]; t[8] = 0; return ps(p, t); }
static char *pd(char *p, int v) { char t[12]; int i = 11; unsigned u = v < 0 ? -(unsigned)v : (unsigned)v; t[i] = 0;
  do { t[--i] = (char)('0' + u % 10); u /= 10; } while (u); if (v < 0) t[--i] = '-'; return ps(p, t + i); }
static void logLine(int append) {   // gLine -> me.txt рядом с EBOOT (открыть-записать-закрыть: строка на карте, даже если дальше встанет)
  char fn[224]; unsigned l = strlen(gDir); if (l + 8 > sizeof fn) return; memcpy(fn, gDir, l); strcpy(fn + l, "me.txt");
  SceUID f = sceIoOpen(fn, PSP_O_WRONLY | PSP_O_CREAT | (append ? PSP_O_APPEND : PSP_O_TRUNC), 0777);
  if (f >= 0) { sceIoWrite(f, gLine, strlen(gLine)); sceIoClose(f); }
}

#define ME_STATE (*(volatile int *)0xbfc00700)   // слово состояния ME в общей памяти (me_wrapper прошивки, MIST: -567 — «наше задание вышло»)
#define ME_DONE_WORD (-567)

// адрес таблицы вызовов ядра ME в его локальной памяти (то же число, что в vendor/me-safe-task/me-stask-mist.c init)
// Только t2img (PSP Slim и новее, у Роба PSP-2000): у старой PSP-1000 (img, 0x0018a210) mistRefreshMe автора пишет значение Slim
// с пометкой «проверить на Phat» — там проба не идёт, строка «table=3» (правило порта)
static unsigned meTableAddr(int table) { return table == ME_CORE_T2_IMG_TABLE ? 0x003ce870u : 0; }

// некэшируемая копия адреса для главного процессора: ядро (0x8…) — kseg1 0xA…; уже kseg1 — как есть; память игры — | 0x40000000.
// TEST 10 на железе (04.10 16:24, crash.txt: exc=7 в meInject): слово DMA лежало в памяти ядра, а ME_UNCACHED(0x88…) = 0xC8… —
// несуществующий адрес, ошибка шины на первой записи. В TEST 8 слово было в памяти игры — там ME_UNCACHED верен
#define KUNC(a) (((unsigned)(a) & 0x1fffffffu) | 0xa0000000u)   // некэшируемая копия адреса ядра (kseg1)
static unsigned uncOf(unsigned a) { unsigned seg = a >> 29; return seg == 4u ? KUNC(a) : seg == 5u ? a : ME_UNCACHED(a & 0x1fffffffu); }
// слово в ячейку таблицы ME через DMACPLUS (как mistInjectSyscall автора), но ожидание конца передачи ограничено (~5 мс)
static int meInject(unsigned tableAddr, int index, unsigned value, unsigned *dmaWord) {
  volatile unsigned *u = (volatile unsigned *)uncOf((unsigned)dmaWord); u[0] = value; __asm__ volatile("sync" : : : "memory");
  int state = sceKernelSuspendDispatchThread(), ok = 0;
  cleanSc2MeChannel();
  dmacplusFromSc((u32)dmaWord, tableAddr + (unsigned)index * 4u, DMACPLUS_BYTE_COUNT_4, 1);
  unsigned t0 = sceKernelGetSystemTimeLow();
  while (sceKernelGetSystemTimeLow() - t0 < 5000u) {
    __asm__ volatile("sync"); if (!hw(0xBC800190)) { ok = 1; break; }
    __asm__ volatile("nop;nop;nop;nop;nop;nop;nop");
  }
  if (!ok) cleanSc2MeChannel();         // не дошло — канал выключить, ячейка как была
  clearPendingOperations();
  sceKernelResumeDispatchThread(state);
  return ok ? 0 : -1;
}

static SceUID evfFind(void) {   // флаг ответа ME прошивки (me_wrapper: «SceMediaEngineRpcWait», uOFW me_wrapper.c initRpc)
  SceUID ids[96]; int n = 0;
  if (sceKernelGetThreadmanIdList(SCE_KERNEL_TMID_EventFlag, ids, 96, &n) < 0) return -1;
  if (n > 96) n = 96;
  for (int i = 0; i < n; i++) {
    SceKernelEventFlagInfo fi; memset(&fi, 0, sizeof fi); fi.size = sizeof fi;
    if (sceKernelReferEventFlagStatus(ids[i], &fi) >= 0 && !strcmp(fi.name, "SceMediaEngineRpcWait")) return ids[i];
  }
  return -1;
}
static unsigned evfPat(SceUID e) {
  SceKernelEventFlagInfo fi; memset(&fi, 0, sizeof fi); fi.size = sizeof fi;
  return e >= 0 && sceKernelReferEventFlagStatus(e, &fi) >= 0 ? fi.currentPattern : 0;
}

static void probe(MeProbeRes *R, unsigned base, unsigned jobs, unsigned toUs) {
  volatile MeBox *ub = (volatile MeBox *)ME_UNCACHED(base);   // ящик — только мимо кэша
  unsigned *dmaWord = (unsigned *)(base + 64);                  // слово для DMACPLUS (своя строка 64 байта)
  unsigned *buf = (unsigned *)(base + 128);                     // буфер задания 64 КБ
  unsigned tAll = sceKernelGetSystemTimeLow();
  sceKernelDcacheWritebackInvalidateRange((void *)base, 128 + ME_PROBE_BYTES);   // в кэше главного ни строки ящика и буфера
  for (int i = 0; i < 16; i++) ((volatile unsigned *)ub)[i] = 0;
  R->mode = 1; R->rtMin = 0xffffffffu;
  // 1 — образ ядра ME (сначала только чтение слова образа: чужой образ или эмулятор — дальше ничего не трогаем)
  R->stage = 1; R->table = meCoreGetTableIdFromWitnessWord();
  unsigned tableAddr = meTableAddr(R->table);
  if (tableAddr) R->st0 = (unsigned)ME_STATE;
  SceUID evf = evfFind(); R->evfFound = evf >= 0;               // флаг ответа ME прошивки — до перезапуска ME (этап 2)
  unsigned evPre = evfPat(evf) & 1u; R->evfPre = (int)evPre;    // поднят ли он уже: тогда наши задания его не трогают
  char *p = ps(gLine, "ME 1 table="); p = pd(p, R->table); p = ps(p, " st0="); p = px(p, R->st0); p = ps(p, " base="); p = px(p, base);
  p = ps(p, " evf="); p = pd(p, R->evfFound ? (int)evPre : -1); ps(p, "\n"); logLine(1);
  if (!tableAddr) { R->init = -1; return; }   // чужой образ: не трогаем (адреса функций ядра ME неизвестны)
  // 2 — MIST: выбрать таблицу, перезапустить ME с прежним вектором (mistRefreshMe автора)
  R->stage = 2; R->init = meSafeKernelTaskMistInit();
  p = ps(gLine, "ME 2 mist init="); p = pd(p, R->init); ps(p, "\n"); logLine(1);
  if (R->init) return;
  sceKernelDelayThread(10000);          // ME поднимается после перезапуска (правило порта: 10 мс с запасом)
  // 3 — адрес meTask в пустую ячейку 13
  R->stage = 3;
  if (meInject(tableAddr, ME_MIST_INDEX, CACHED_KERNEL_MASK | (unsigned)meTask, dmaWord)) { R->init = -2; ps(gLine, "ME 3 inject timeout\n"); logLine(1); return; }
  ps(gLine, "ME 3 inject ok\n"); logLine(1);
  // 4 — задания
  R->stage = 4; MistTrigger trig = {ME_MIST_INDEX, (void *)ub};
  for (unsigned k = 1; k <= jobs; k++) {
    unsigned want;
    for (unsigned i = 0; i < ME_PROBE_WORDS; i++) buf[i] = meJobWord(k, i);
    want = meJobSum(buf, ME_PROBE_WORDS);                       // та же функция на главном процессоре
    sceKernelDcacheWritebackInvalidateRange(buf, ME_PROBE_BYTES);
    ub->buf = (unsigned)buf; ub->words = ME_PROBE_WORDS; ub->sent = k; __asm__ volatile("sync" : : : "memory");
    unsigned t0 = sceKernelGetSystemTimeLow(), dt = 0; int got = 0;
    meSafeKernelTaskMistTrigger(&trig);
    for (;;) {
      dt = sceKernelGetSystemTimeLow() - t0;
      if (ub->done == k && ME_STATE == ME_DONE_WORD) { got = 1; break; }   // ответ и выход ME из нашей функции
      if (dt >= toUs) break;
      if (dt > 2000u) sceKernelDelayThread(200);                // первые 2 мс — опрос подряд (точное время), дальше — уступая
    }
    R->jobs = (int)k;
    if (!got) { R->timeout = 1; R->timeoutJob = (int)k; break; }
    R->ok++; if (ub->sum == want) R->sumOk++;
    if (dt < R->rtMin) { R->rtMin = dt; }
    if (dt > R->rtMax) { R->rtMax = dt; }
    R->rtSum += dt;
    if (evf >= 0 && !evPre) {   // флаг прошивки от нашего задания поднимается прерыванием ME — бывает позже ответа в ящике:
      u32 pat = 0; SceUInt to = 2000;   // ждать до 2 мс и снять ожиданием (иначе следующий вызов ME прошивки — кадр sceJpeg — вернётся раньше ответа)
      if (sceKernelWaitEventFlag(evf, 1u, PSP_EVENT_WAITOR | PSP_EVENT_WAITCLEAR, &pat, &to) >= 0) R->evf++;
    }
  }
  R->status = ub->status; R->fcsr0 = ub->fcsr0; R->fcsr1 = ub->fcsr1; R->beat = ub->beat; R->st1 = (unsigned)ME_STATE;
  p = ps(gLine, "ME 4 jobs="); p = pd(p, R->jobs); p = ps(p, " ok="); p = pd(p, R->ok); p = ps(p, " sum_ok="); p = pd(p, R->sumOk);
  p = ps(p, " rt_us_min/max="); p = pd(p, R->ok ? (int)R->rtMin : 0); p = ps(p, "/"); p = pd(p, (int)R->rtMax);
  p = ps(p, " timeout="); p = pd(p, R->timeout); p = ps(p, " status="); p = px(p, R->status); p = ps(p, " fpu=");
  p = px(p, R->fcsr0); p = ps(p, ">"); p = px(p, R->fcsr1); p = ps(p, " evf="); p = pd(p, R->evf); p = ps(p, " st1="); p = px(p, R->st1);
  ps(p, "\n"); logLine(1);
  if (!R->timeout) {                    // ME не ответил: ячейку и слово состояния не трогаем — ME, возможно, ещё в нашем коде
    // 5 — уборка: ячейка снова пустая (как в образе прошивки), слово состояния — как до пробы
    R->stage = 5;
    int rc = meInject(tableAddr, ME_MIST_INDEX, 0, dmaWord);
    ME_STATE = (int)R->st0; __asm__ volatile("sync" : : : "memory");
    p = ps(gLine, "ME 5 clean slot="); p = pd(p, rc); ps(p, "\n"); logLine(1);
  }
  // 6 — флаг ответа ME прошивки: пауза 1 мс (позднее прерывание последнего задания), поднят, а до пробы не был, — снять;
  // итог — в me.txt: следующий вызов ME прошивки (кадры ролика sceJpeg) не должен застать чужой поднятый флаг
  int cleared = 0;
  if (evf >= 0) {
    sceKernelDelayThread(1000);
    if ((evfPat(evf) & 1u) && !evPre) { sceKernelClearEventFlag(evf, ~1u); cleared = 1; }
  }
  R->evfEnd = evf >= 0 ? (int)(evfPat(evf) & 1u) : -1; R->evfCleared = cleared;
  R->msTotal = (sceKernelGetSystemTimeLow() - tAll) / 1000u;
  p = ps(gLine, "ME 6 evf found="); p = pd(p, R->evfFound); p = ps(p, " pre="); p = pd(p, R->evfPre); p = ps(p, " waits="); p = pd(p, R->evf);
  p = ps(p, " cleared="); p = pd(p, cleared); p = ps(p, " end="); p = pd(p, R->evfEnd); p = ps(p, " ms="); p = pd(p, (int)R->msTotal);
  ps(p, "\n"); logLine(1);
}

// ---------------------------------------------------------------- правка 276: режим службы (звук на ME, флаг-файл meaudio)
// Правка 313: схема памяти (mebox.h ME_MEM) и два клиента — звук (0) и частицы (1). На ME одно задание за раз: flBox/flSeq —
// задание, которое сейчас у ME (любого клиента); новое не уходит, пока прошлое не вышло из ME (ответ в ящике и -567 в слове состояния)
static SceUID svcEvf = -1; static unsigned svcEvPre = 1, svcSt0;
static int svcScheme; static SceUID svcKuid = -1; static unsigned svcFn;   // svcFn — функция ME (04.10: meGameTask игры)
static unsigned svcKbox[2];               // ящики клиентов в памяти ядра (кэшируемые адреса, по 64 байта)
static MixJob *svcKjob;                   // задание звука в памяти ядра (схема ME_MEM_KERN)
static unsigned svcUjob[2], svcSeq[2], svcOut[2];
static volatile MeBox *flBox; static unsigned flSeq;
static int svcBusy(void) {
  if (!flBox) return 0;
  if (flBox->done == flSeq && ME_STATE == ME_DONE_WORD) { flBox = 0; return 0; }
  return 1;
}
// задание — на ME; режим ядра (игра зовёт через kuKernelCall). Схема 0: a1 — некэшируемый адрес ящика в памяти игры (игра его
// заполнила), a2/a3 не нужны. Схемы 1–3: a1 — клиент | вид задания << 8, a2 — адрес задания в памяти игры, a3 — его размер; ящик
// клиента в ядре пишет модуль. Флаг ответа ME прошивки от прошлого задания — снять (его не должен застать следующий вызов прошивки).
// -> номер задания; ME_SVC_BUSY — у ME ещё прошлое задание (клиент считает сам); -2 — не тот размер задания
int meSvcKick(unsigned a1, unsigned a2, unsigned a3) {
  int kb3 = ME_SCHEME_KBOX(svcScheme);
  unsigned c = a1 & 1u, kind = (a1 >> 8) & 0xffu, job = 0;
  if (kb3) {
    job = meUserAddr(svcScheme, a2);
    if (kind == ME_KIND_MIX && (svcScheme & 3) == ME_MEM_KERN) {   // задание звука — в ядро (только звучащие голоса и окна)
      if (a3 != sizeof(MixJob) || !svcKjob) return -2;
      if (svcBusy() && flBox == (volatile MeBox *)KUNC(svcKbox[0])) return ME_SVC_BUSY;   // прошлое задание звука ещё считается
      mixJobIn(svcKjob, (const MixJob *)a2);
      svcKjob->data = (const unsigned char *)meUserAddr(svcScheme, (unsigned)svcKjob->data);
      sceKernelDcacheWritebackInvalidateRange(svcKjob, sizeof(MixJob));
      job = (unsigned)svcKjob;
    }
  }
  int state = sceKernelSuspendDispatchThread(), r;
  if (svcBusy()) r = ME_SVC_BUSY;
  else if (!kb3) {
    volatile MeBox *ub = (volatile MeBox *)a1;
    flBox = ub; flSeq = ub->sent; r = (int)flSeq;
  } else {
    volatile MeBox *kb = (volatile MeBox *)KUNC(svcKbox[c]);
    svcUjob[c] = a2; svcOut[c] = 0;
    kb->kind = kind; kb->job = job; kb->words = a3; kb->sum = 0; kb->sent = ++svcSeq[c]; __asm__ volatile("sync" : : : "memory");
    flBox = kb; flSeq = svcSeq[c]; r = (int)flSeq;
    a1 = (svcScheme & 3) == ME_MEM_KBOXU ? KUNC(svcKbox[c]) : svcKbox[c];   // адрес ящика для ME: кэшируемый (1, 3) или нет (2)
  }
  if (r != ME_SVC_BUSY) {
    if (svcEvf >= 0 && !svcEvPre) sceKernelClearEventFlag(svcEvf, ~1u);
    MistTrigger trig = {ME_MIST_INDEX, (void *)a1};
    meSafeKernelTaskMistTrigger(&trig);
  }
  sceKernelResumeDispatchThread(state);
  return r;
}
// схемы 1–3: -> «сделано» клиента (биты 0–30) и бит 31 — задание не посчитано (модуль и игра разных сборок, ME_MIX_BADSIZE);
// ME_MEM_KERN — итог звука переносится в память игры (одно 32-битное слово: ret1 kuKernelCall)
unsigned meSvcPoll(unsigned c) {
  c &= 1u;
  if (!svcKbox[c]) return 0;
  volatile MeBox *kb = (volatile MeBox *)KUNC(svcKbox[c]);
  unsigned done = kb->done, sum = kb->sum;
  if (done == svcSeq[c] && !svcOut[c] && kb->kind == ME_KIND_MIX && (svcScheme & 3) == ME_MEM_KERN && sum != ME_MIX_BADSIZE && svcKjob) {
    sceKernelDcacheInvalidateRange(svcKjob, sizeof(MixJob));
    mixJobOut((MixJob *)svcUjob[c], svcKjob); svcOut[c] = 1;
  }
  return (done & 0x7fffffffu) | (sum == ME_MIX_BADSIZE ? 0x80000000u : 0u);
}
// ME звуку больше не отдаём (ролик sceJpeg, сон, выход): последнее задание уже забрано; ждать флаг до 2 мс и снять, слово
// состояния ME — как до службы. -> бит 0: флаг снят ожиданием, бит 1: флаг поднят и после
int meSvcQuiesce(void) {
  int r = 0;
  if (svcEvf >= 0 && !svcEvPre) {
    u32 pat = 0; SceUInt to = 2000;
    if (sceKernelWaitEventFlag(svcEvf, 1u, PSP_EVENT_WAITOR | PSP_EVENT_WAITCLEAR, &pat, &to) >= 0) r |= 1;
    if (evfPat(svcEvf) & 1u) r |= 2;
  }
  if (!svcBusy()) { flBox = 0; ME_STATE = (int)svcSt0; __asm__ volatile("sync" : : : "memory"); }   // задание в ME — слово не трогаем
  return r;
}
static void svcStart(MeSvcRes *R, unsigned *dmaWord) {   // dmaWord — своя строка 64 байта в памяти игры (источник DMA, как у автора)
  unsigned tAll = sceKernelGetSystemTimeLow();
  R->stage = 1; R->table = meCoreGetTableIdFromWitnessWord();
  unsigned tableAddr = meTableAddr(R->table);
  if (tableAddr) svcSt0 = R->st0 = (unsigned)ME_STATE;
  svcEvf = evfFind(); R->evfFound = svcEvf >= 0; svcEvPre = evfPat(svcEvf) & 1u; R->evfPre = (int)svcEvPre;
  char *p = ps(gLine, "MEA 1 table="); p = pd(p, R->table); p = ps(p, " st0="); p = px(p, R->st0); p = ps(p, " evf=");
  p = pd(p, R->evfFound ? (int)svcEvPre : -1); p = ps(p, " scheme="); p = pd(p, svcScheme); ps(p, "\n"); logLine(1);
  if (!tableAddr) { R->init = -1; return; }
  if (ME_SCHEME_KBOX(svcScheme)) {        // правка 313: ящики клиентов (2 × 64) и задание звука (схема 3) — в памяти ядра модуля
    unsigned need = 128 + ((svcScheme & 3) == ME_MEM_KERN ? sizeof(MixJob) : 0) + 64;
    svcKuid = sceKernelAllocPartitionMemory(1, "sharmeS", PSP_SMEM_Low, need, NULL);
    if (svcKuid < 0) { R->init = -3; p = ps(gLine, "MEA 1 kmem fail "); p = px(p, (unsigned)svcKuid); ps(p, "\n"); logLine(1); return; }
    unsigned b = ((unsigned)sceKernelGetBlockHeadAddr(svcKuid) + 63u) & ~63u;
    svcKbox[0] = b; svcKbox[1] = b + 64;
    if ((svcScheme & 3) == ME_MEM_KERN) svcKjob = (MixJob *)(b + 128);
    for (unsigned a = b; a < b + need - 64; a += 4) *(volatile unsigned *)KUNC(a) = 0;
    sceKernelDcacheWritebackInvalidateRange((void *)b, need - 64);
    R->kbox = b; R->kjob = (unsigned)svcKjob;
  }
  R->stage = 2; R->init = meSafeKernelTaskMistInit();
  p = ps(gLine, "MEA 2 mist init="); p = pd(p, R->init); ps(p, "\n"); logLine(1);
  if (R->init) return;
  sceKernelDelayThread(10000);          // ME поднимается после перезапуска (как в пробе)
  sceKernelDcacheWritebackAll();        // код и таблицы модуля (mixdsp.h, fxdsp.h, libm) — в памяти: ME читает их своим кэшем
  R->stage = 3;
  if (!svcFn) svcFn = (unsigned)meTask;   // старая игра без gameFn — функция модуля (на железе не работает: ядро ME не видит)
  if (meInject(tableAddr, ME_MIST_INDEX, CACHED_KERNEL_MASK | svcFn, dmaWord)) { R->init = -2; ps(gLine, "MEA 3 inject timeout\n"); logLine(1); return; }
  R->kick = (unsigned)meSvcKick; R->quiesce = (unsigned)meSvcQuiesce; R->poll = (unsigned)meSvcPoll; R->scheme = svcScheme;
  R->msTotal = (sceKernelGetSystemTimeLow() - tAll) / 1000u;
  p = ps(gLine, "MEA 3 inject ok job="); p = pd(p, (int)sizeof(MixJob)); p = ps(p, " fx="); p = pd(p, (int)sizeof(FxJob));
  p = ps(p, " fn="); p = px(p, CACHED_KERNEL_MASK | svcFn); p = ps(p, " kbox="); p = px(p, svcKbox[0]); p = ps(p, " kjob="); p = px(p, (unsigned)svcKjob);
  p = ps(p, " ms="); p = pd(p, (int)R->msTotal); ps(p, "\n"); logLine(1);
}

// ---------------------------------------------------------------- TEST 10: лесенка (mebox.h MeLadder*), ступени по одной
static struct {
  int inited, injected, stuck; unsigned table, tableAddr, st0; SceUID evf; unsigned evPre;
  SceUID kuid, huid; unsigned kmem, kbox, kdma, kbuf, low, lowBytes, hi;   // kbox/kdma/kbuf — кэшируемые адреса ядра
  MeLadderRes *R; unsigned gameFn;
} L = {0, 0, 0, 0, 0, 0, -1, 1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0};
static void lOut(int code) {            // строка ступени: me.txt (открыть-записать-закрыть) и в итог игре
  logLine(1);
  if (L.R) { MeLadderRes *u = (MeLadderRes *)KUNC(L.R); unsigned n = strlen(gLine); if (n > sizeof u->line - 1) n = sizeof u->line - 1;
    memcpy((void *)u->line, gLine, n); u->line[n] = 0; u->last = code; u->stuck = L.stuck; }
}
static const char *lZone(unsigned a) {  // где лежит адрес: ядро / нижняя память игры / верхние 32 МБ (PSP-2000+)
  a &= 0x1fffffffu; return a < 0x08800000u ? "kernel" : a < 0x0a000000u ? "low" : "high";
}
static unsigned lSt[4];   // TEST 11: ME_STATE до запуска и через 1/10/100 мс после (реагирует ли ME вообще)
// одно задание: ящик box (адрес, который получит ME), его некэшируемая копия ub для главного; kind, буфер buf (кэшируемый)
static int lJob(unsigned box, volatile MeBox *ub, unsigned kind, unsigned buf, unsigned words, unsigned k, unsigned toUs, unsigned *rt, unsigned *sumOk) {
  unsigned want = 0;
  if (kind == ME_KIND_SUM) {
    unsigned *b = (unsigned *)buf;
    for (unsigned i = 0; i < words; i++) b[i] = meJobWord(k, i);
    want = meJobSum(b, words);
    sceKernelDcacheWritebackInvalidateRange(b, words * 4);
  }
  ub->kind = kind; ub->buf = buf; ub->words = words; ub->sum = 0; ub->sent = k; __asm__ volatile("sync" : : : "memory");
  if (L.evf >= 0 && !L.evPre) sceKernelClearEventFlag(L.evf, ~1u);   // флаг ответа прошивки от прошлого задания — снять
  MistTrigger trig = {ME_MIST_INDEX, (void *)box};
  unsigned t0 = sceKernelGetSystemTimeLow(), dt, si = 0;
  lSt[0] = (unsigned)ME_STATE; lSt[1] = lSt[2] = lSt[3] = lSt[0];   // TEST 11: слово состояния ME сразу, через 1, 10 и 100 мс
  meSafeKernelTaskMistTrigger(&trig);
  for (;;) {
    dt = sceKernelGetSystemTimeLow() - t0;
    while (si < 3 && dt >= (si == 0 ? 1000u : si == 1 ? 10000u : 100000u)) lSt[1 + si++] = (unsigned)ME_STATE;
    if (ub->done == k && ME_STATE == ME_DONE_WORD) break;
    if (dt >= toUs) return -1;
    if (dt > 2000u) sceKernelDelayThread(200);
  }
  *rt = dt;
  if (kind == ME_KIND_SUM ? ub->sum == want : ub->sum == 0x7e57u) (*sumOk)++;
  if (L.evf >= 0 && !L.evPre) { u32 pat = 0; SceUInt to = 2000; sceKernelWaitEventFlag(L.evf, 1u, PSP_EVENT_WAITOR | PSP_EVENT_WAITCLEAR, &pat, &to); }
  return 0;
}
// серия заданий -> строка «ML n …»
static int lSeriesW(int n, const char *what, unsigned box, unsigned kind, unsigned buf, unsigned jobs, unsigned words);
static int lSeries(int n, const char *what, unsigned box, unsigned kind, unsigned buf, unsigned jobs) { return lSeriesW(n, what, box, kind, buf, jobs, buf ? ME_LADDER_BYTES / 4 : 0); }
static int lSeriesW(int n, const char *what, unsigned box, unsigned kind, unsigned buf, unsigned jobs, unsigned words) {
  volatile MeBox *ub = (volatile MeBox *)uncOf(box);
  unsigned ok = 0, sumOk = 0, rmin = 0xffffffffu, rmax = 0, rsum = 0;
  for (int i = 0; i < 16; i++) ((volatile unsigned *)ub)[i] = 0;
  __asm__ volatile("sync" : : : "memory");
  for (unsigned k = 1; k <= jobs; k++) {
    unsigned rt = 0;
    if (lJob(box, ub, kind, buf, words, k, 200000u, &rt, &sumOk)) { L.stuck = 1; break; }
    ok++; rsum += rt; if (rt < rmin) rmin = rt; if (rt > rmax) rmax = rt;
  }
  char *p = ps(gLine, "ML "); p = pd(p, n); p = ps(p, " "); p = ps(p, what); p = ps(p, " box="); p = px(p, box); p = ps(p, " ");
  p = ps(p, lZone(box)); if (buf) { p = ps(p, " buf="); p = px(p, buf); p = ps(p, " "); p = ps(p, lZone(buf)); }
  p = ps(p, " ok="); p = pd(p, (int)ok); p = ps(p, "/"); p = pd(p, (int)jobs); p = ps(p, " sum_ok="); p = pd(p, (int)sumOk);
  p = ps(p, " rt_us_min/avg/max="); p = pd(p, ok ? (int)rmin : 0); p = ps(p, "/"); p = pd(p, ok ? (int)(rsum / ok) : 0); p = ps(p, "/"); p = pd(p, (int)rmax);
  p = ps(p, " status="); p = px(p, ub->status); p = ps(p, " beat="); p = pd(p, (int)ub->beat); p = ps(p, " st="); p = px(p, (unsigned)ME_STATE);
  p = ps(p, " st0/1/10/100ms="); for (int i = 0; i < 4; i++) { p = px(p, lSt[i]); if (i < 3) p = ps(p, "/"); }
  p = ps(p, L.stuck ? " STUCK\n" : "\n"); lOut(L.stuck ? -1 : (int)ok);
  return L.stuck ? -1 : 0;
}
// TEST 13: «всё одним вызовом», как проба TEST 8 (там ME отозвался: ME_STATE 0 → 1): перезапуск MIST, 10 мс, ячейка, сразу задание.
// 10 — слово DMA и ящик в памяти ядра; 11 — оба в нижней памяти игры (ящик | 0x40000000); 12 — ящик в верхних 32 МБ, как TEST 8.
// ME в TEST 10–12 задание даже не принимал (слово состояния не менялось) — наш код он не исполняет, поэтому эти ступени идут и после «stuck»
static int lComboFn(int n, unsigned dma, unsigned box, const char *what, unsigned fn);
static int lCombo(int n, unsigned dma, unsigned box, const char *what) { return lComboFn(n, dma, box, what, (unsigned)meTask); }
static int lComboFn(int n, unsigned dma, unsigned box, const char *what, unsigned fn) {
  int init = meSafeKernelTaskMistInit(); L.inited = init == 0;
  sceKernelDelayThread(10000); unsigned s10 = (unsigned)ME_STATE;
  sceKernelDcacheWritebackAll();
  int rc = init ? -9 : meInject(L.tableAddr, ME_MIST_INDEX, CACHED_KERNEL_MASK | fn, (unsigned *)dma);
  L.injected = rc == 0; L.stuck = 0;
  char *p;
  if (init || rc) { p = ps(gLine, "ML "); p = pd(p, n); p = ps(p, " combo "); p = ps(p, what); p = ps(p, " init="); p = pd(p, init);
    p = ps(p, " inject="); p = pd(p, rc); ps(p, "\n"); lOut(-10); return -10; }
  p = ps(gLine, "ML "); p = pd(p, n); p = ps(p, " combo "); p = ps(p, what); p = ps(p, " dma="); p = px(p, dma); p = ps(p, " ");
  p = ps(p, lZone(dma)); p = ps(p, " fn="); p = px(p, CACHED_KERNEL_MASK | fn); p = ps(p, " "); p = ps(p, lZone(fn));
  p = ps(p, " st_after_init="); p = px(p, s10); ps(p, "\n"); logLine(1);
  char tag[48]; char *q = tag; const char *w = "combo "; while (*w) *q++ = *w++; w = what; while (*w && q < tag + 40) *q++ = *w++; *q = 0;
  return lSeries(n, tag, box, ME_KIND_TINY, 0, 1);
}
int meLadderStep(int n) {
  char *p;
  if (n >= 10 && n <= 21) {
    if (!L.tableAddr) { ps(gLine, "ML 1x skip: table\n"); lOut(-3); return -3; }
    if (n == 10) return lCombo(10, L.kdma, L.kbox, "kernel");
    if (!L.low) { ps(gLine, "ML 11 skip: no low\n"); lOut(-6); return -6; }
    unsigned lowDma = L.low + ME_LADDER_BYTES - 128, lowBox = L.low + ME_LADDER_BYTES - 64;   // хвост нижнего буфера: своя строка 64
    if (n == 11) return lCombo(11, lowDma, ME_UNCACHED(lowBox), "low");
    // TEST 13 на железе: 11 — ME задание принял (ME_STATE 0 → 1), но не закончил: ящик | 0x40000000 ME, видимо, не видит.
    // 13 — ящик кэшируемым адресом памяти игры (как poc-mist автора: ME сбрасывает строку сам); 14 — тот же ящик через kseg0 (0x88…)
    if (n == 13) return lCombo(13, lowDma, lowBox, "low-cached");
    if (n == 14) return lCombo(14, lowDma, CACHED_KERNEL_MASK | lowBox, "low-kseg0");
    // TEST 15: функция ME в памяти игры (meGameTask), ящик — кэшируемый адрес памяти игры; 16 — то же, ящик | 0x40000000
    if (!L.gameFn) { ps(gLine, "ML 15 skip: no game fn\n"); lOut(-6); return -6; }
    if (n == 15) return lComboFn(15, lowDma, lowBox, "gamefn-cached", L.gameFn);
    if (n == 16) return lComboFn(16, lowDma, ME_UNCACHED(lowBox), "gamefn-uncached", L.gameFn);
    // TEST 16 (TEST 15 на железе 22:16: ME ответил — функция в памяти игры, 5 мкс, сумма сошлась): работа ME из памяти игры.
    // Ячейка уже наша (ступень 15/16). 17 — сумма буфера нижней памяти ×10 (буфер без хвоста под ящик), 18 — буфер верхних 32 МБ ×10,
    // 19 — ×200 (время), 20 — пустое задание после ролика (стёр ли его ролик ячейку), 21 — перезапуск + ячейка + задание после ролика
    L.stuck = 0;
    if (n == 17) return lSeriesW(17, "gamefn sum low x10", lowBox, ME_KIND_SUM, L.low, 10, (ME_LADDER_BYTES - 256) / 4);
    if (n == 18) { if (!L.hi) { ps(gLine, "ML 18 skip: no high\n"); lOut(-6); return -6; }
      return lSeriesW(18, "gamefn sum high x10", lowBox, ME_KIND_SUM, L.hi, 10, ME_LADDER_BYTES / 4); }
    if (n == 19) return lSeriesW(19, "gamefn sum low x200", lowBox, ME_KIND_SUM, L.low, 200, (ME_LADDER_BYTES - 256) / 4);
    if (n == 20) return lSeriesW(20, "gamefn tiny after movie", lowBox, ME_KIND_TINY, 0, 1, 0);
    if (n == 21) return lComboFn(21, lowDma, lowBox, "gamefn again", L.gameFn);
    if (!L.hi) { ps(gLine, "ML 12 skip: no high\n"); lOut(-6); return -6; }
    return lCombo(12, lowDma, ME_UNCACHED(L.hi + ME_LADDER_BYTES - 64), "high-box");
  }
  if (L.stuck && n != 99) { p = ps(gLine, "ML "); p = pd(p, n); ps(p, " skip: ME stuck\n"); lOut(-2); return -2; }
  if (n == 1) {                         // перезапуск ME методом MIST (вектор сброса прежний)
    if (!L.tableAddr) { ps(gLine, "ML 1 skip: table\n"); lOut(-3); return -3; }
    int init = meSafeKernelTaskMistInit(); L.inited = init == 0;
    sceKernelDelayThread(10000); unsigned s10 = (unsigned)ME_STATE; sceKernelDelayThread(190000); unsigned s200 = (unsigned)ME_STATE;
    p = ps(gLine, "ML 1 mist init="); p = pd(p, init); p = ps(p, " st="); p = px(p, L.st0); p = ps(p, ">"); p = px(p, s10); p = ps(p, ">"); p = px(p, s200);
    ps(p, "\n"); lOut(init); return init;
  }
  if (!L.inited) { p = ps(gLine, "ML "); p = pd(p, n); ps(p, " skip: no mist\n"); lOut(-4); return -4; }
  if (n == 2) {                         // адрес meTask в пустую ячейку 13
    sceKernelDcacheWritebackAll();
    int rc = meInject(L.tableAddr, ME_MIST_INDEX, CACHED_KERNEL_MASK | (unsigned)meTask, (unsigned *)L.kdma);
    L.injected = rc == 0;
    p = ps(gLine, "ML 2 inject "); p = ps(p, rc ? "timeout" : "ok"); p = ps(p, " fn="); p = px(p, CACHED_KERNEL_MASK | (unsigned)meTask);
    p = ps(p, " "); p = ps(p, lZone((unsigned)meTask)); ps(p, "\n"); lOut(rc); return rc;
  }
  if (!L.injected && n != 99) { p = ps(gLine, "ML "); p = pd(p, n); ps(p, " skip: no slot\n"); lOut(-5); return -5; }
  switch (n) {
    case 3: return lSeries(3, "tiny cached", L.kbox, ME_KIND_TINY, 0, 1);
    case 4: return lSeries(4, "tiny uncached x20", KUNC(L.kbox), ME_KIND_TINY, 0, 20);
    case 5: return lSeries(5, "sum kernel x10", KUNC(L.kbox), ME_KIND_SUM, L.kbuf, 10);
    case 6: return lSeries(6, "sum kernel x200", KUNC(L.kbox), ME_KIND_SUM, L.kbuf, 200);
    case 7:
      if (!L.low || L.lowBytes < ME_LADDER_BYTES) { ps(gLine, "ML 7 skip: no low buffer\n"); lOut(-6); return -6; }
      return lSeries(7, "sum low x10", KUNC(L.kbox), ME_KIND_SUM, L.low, 10);
    case 8:
      if (!L.hi) { ps(gLine, "ML 8 skip: no high buffer\n"); lOut(-6); return -6; }
      return lSeries(8, "sum high x10", KUNC(L.kbox), ME_KIND_SUM, L.hi, 10);
    case 9:                             // как TEST 8: ящик в верхних 32 МБ, адрес | 0x40000000
      if (!L.hi) { ps(gLine, "ML 9 skip: no high buffer\n"); lOut(-6); return -6; }
      return lSeries(9, "tiny high-box", ME_UNCACHED(L.hi + ME_LADDER_BYTES - 64), ME_KIND_TINY, 0, 1);
    case 99: {                          // уборка: ячейка пустая, слово состояния — как до лесенки, флаг прошивки снят
      int rc = 1;
      if (!L.stuck && L.injected) { rc = meInject(L.tableAddr, ME_MIST_INDEX, 0, (unsigned *)L.kdma); if (!rc) L.injected = 0; }
      if (!L.stuck) { ME_STATE = (int)L.st0; __asm__ volatile("sync" : : : "memory"); }
      int cl = 0; if (L.evf >= 0 && !L.evPre && (evfPat(L.evf) & 1u)) { sceKernelClearEventFlag(L.evf, ~1u); cl = 1; }
      p = ps(gLine, "ML 99 clean slot="); p = pd(p, rc); p = ps(p, " evf_cleared="); p = pd(p, cl); p = ps(p, " st="); p = px(p, (unsigned)ME_STATE);
      ps(p, L.stuck ? " (ME stuck: slot left)\n" : "\n"); lOut(rc); return rc;
    }
  }
  p = ps(gLine, "ML "); p = pd(p, n); ps(p, " unknown\n"); lOut(-7); return -7;
}
static int ladderStart(const MeLadderArgs *a) {
  L.R = (MeLadderRes *)a->res; L.low = a->lowBuf; L.lowBytes = a->lowBytes; L.gameFn = a->gameFn;
  ps(gLine, "ML 0 sharme.prx ladder\n"); logLine(0);
  L.table = (unsigned)meCoreGetTableIdFromWitnessWord(); L.tableAddr = meTableAddr((int)L.table);
  if (L.tableAddr) L.st0 = (unsigned)ME_STATE;
  L.evf = evfFind(); L.evPre = evfPat(L.evf) & 1u;
  // память ядра: ящик 64 + слово DMA 64 + буфер 16 КБ (выровнено на 64)
  L.kuid = sceKernelAllocPartitionMemory(1, "sharmeL", PSP_SMEM_Low, 128 + ME_LADDER_BYTES + 64, NULL);
  if (L.kuid >= 0) { L.kmem = (unsigned)sceKernelGetBlockHeadAddr(L.kuid); unsigned b = (L.kmem + 63u) & ~63u;
    L.kbox = b; L.kdma = b + 64; L.kbuf = b + 128; sceKernelDcacheWritebackInvalidateRange((void *)b, 128 + ME_LADDER_BYTES); }
  L.huid = sceKernelAllocPartitionMemory(2, "sharmeH", PSP_SMEM_High, ME_LADDER_BYTES + 64, NULL);
  if (L.huid >= 0) { unsigned h = (unsigned)sceKernelGetBlockHeadAddr(L.huid); L.hi = (h + 63u) & ~63u;
    if ((L.hi & 0x1fffffffu) < 0x0a000000u) { char *q = ps(gLine, "ML 0 note: high block below 0x0A000000 at "); q = px(q, L.hi); ps(q, "\n"); logLine(1); } }
  char *p = ps(gLine, "ML 0 table="); p = pd(p, (int)L.table); p = ps(p, " st0="); p = px(p, L.st0); p = ps(p, " evf=");
  p = pd(p, L.evf >= 0 ? (int)L.evPre : -1); p = ps(p, " fn="); p = px(p, (unsigned)meTask); p = ps(p, " kbox="); p = px(p, L.kbox);
  p = ps(p, " low="); p = px(p, L.low); p = ps(p, " "); p = ps(p, L.low ? lZone(L.low) : "-"); p = ps(p, " high="); p = px(p, L.hi);
  p = ps(p, " "); p = ps(p, L.hi ? lZone(L.hi) : "-"); p = ps(p, " res="); p = px(p, a->res); p = ps(p, " "); p = ps(p, lZone(a->res)); ps(p, "\n");
  if (!L.kbox) { L.stuck = 1; }         // без памяти ядра — ступеней не будет
  lOut(L.kbox ? 0 : -8);
  MeLadderRes *u = (MeLadderRes *)KUNC(L.R); u->step = (unsigned)meLadderStep; u->magic = ME_LADDER_MAGIC;
  return 0;
}

int module_start(SceSize args, void *argp) {
  if (argp && args >= sizeof(MeLadderArgs) && ((const MeLadderArgs *)argp)->magic == ME_LADDER_MAGIC) {   // TEST 10: лесенка
    MeLadderArgs a; memcpy(&a, argp, sizeof a); a.dir[sizeof a.dir - 1] = 0;
    if ((a.res & 63u) || a.res < 0x08800000u || a.res + sizeof(MeLadderRes) > 0x0c000000u) return 1;
    strcpy(gDir, a.dir);
    return ladderStart(&a);             // в памяти остаёмся: ступени зовёт игра (kuKernelCall)
  }
  if (argp && args >= sizeof(MeSvcArgs) && ((const MeSvcArgs *)argp)->magic == ME_SVC_MAGIC) {   // правка 276: служба звука
    MeSvcArgs s; memcpy(&s, argp, sizeof s); s.dir[sizeof s.dir - 1] = 0;
    if ((s.res & 63u) || sizeof(MeSvcRes) > 64 || s.res < 0x08800000u || s.res + 128 > 0x0c000000u) return 1;   // итог 64 + слово DMA 64
    if (s.scheme < 0 || s.scheme > 7) return 1;
    svcScheme = s.scheme; svcFn = s.gameFn;   // 04.10: функция ME в памяти игры (meGameTask)
    strcpy(gDir, s.dir);
    MeSvcRes *R = (MeSvcRes *)s.res; memset(R, 0, sizeof *R);
    ps(gLine, "MEA 0 sharme.prx service\n"); logLine(0);
    svcStart(R, (unsigned *)(s.res + 64));
    meSvcPublish(R, sceKernelDcacheWritebackRange);
    return 0;                           // в памяти остаёмся: задача в ячейке ME — наш код
  }
  MeProbeArgs a; memset(&a, 0, sizeof a);
  if (!argp || args < sizeof a) return 1;
  memcpy(&a, argp, sizeof a); a.dir[sizeof a.dir - 1] = 0;
  if (a.magic != ME_PROBE_MAGIC) return 1;
  strcpy(gDir, a.dir);
  // память игры: ящик (64) + слово DMA (64) + буфер 64 КБ, выровнено на 64, целиком в пользовательской памяти
  unsigned base = a.res + ((sizeof(MeProbeRes) + 63u) & ~63u);
  if ((a.res & 63u) || a.res < 0x08800000u || base + 128 + ME_PROBE_BYTES > 0x0c000000u) return 1;   // PSP-2000+: игра до 0x0c000000
  MeProbeRes *R = (MeProbeRes *)a.res; memset(R, 0, sizeof *R);
  unsigned jobs = a.jobs && a.jobs <= 1000 ? a.jobs : ME_PROBE_JOBS, to = a.timeoutUs ? a.timeoutUs : ME_PROBE_TIMEOUT_US;
  ps(gLine, "ME 0 sharme.prx start\n"); logLine(0);
  probe(R, base, jobs, to);
  R->magic = ME_PROBE_MAGIC;
  return 0;                             // в памяти остаёмся
}
int module_stop(SceSize args, void *argp) { return 0; }
