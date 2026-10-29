// Media Engine, ступень 0 — проба (правки Роба 269/273/276: «понять, как на PSP работает Media Engine, и использовать его во
// время игры»; план docs/ME_ПЛАН_2026-10-03.md, правила конвейера — docs/handoff/ПЛАН_ВЕДУЩЕГО_2026-10-04.md §3).
// Общее для трёх мест: модуль ядра viewer/me/sharme.c (ведёт пробу и сам код на ME), сторона игры viewer/me/meprobe.c
// (флаг сценария «meprobe») и проверка на Маке tests/me/sum_test.c. Здесь нет вызовов системы: задание meJobSum считает
// одинаково на ME, на главном процессоре PSP и на Маке (бит в бит) — правило конвейера ME.
#ifndef MEBOX_H
#define MEBOX_H

#define ME_PROBE_MAGIC 0x3150454du      // "MEP1"
#define ME_PROBE_JOBS 100               // заданий «сумма буфера»
#define ME_PROBE_BYTES 65536            // буфер задания: 64 КБ
#define ME_PROBE_WORDS (ME_PROBE_BYTES / 4)
#define ME_PROBE_TIMEOUT_US 50000       // нет ответа за 50 мс — «ME timeout», дальше без ME
#define ME_MIST_INDEX 13                // пустая ячейка таблицы вызовов ядра ME (t2img: [013] = 0, список автора MIST)
#define ME_UNCACHED(a) (0x40000000u | (unsigned)(a))   // некэшируемая копия адреса пользовательской памяти

// Почтовый ящик: 64 байта, выровнен на 64, обе стороны ходят только через ME_UNCACHED. «sent» пишет только главный
// процессор, «done» и выходы — только ME (кэши процессоров не согласованы: общая строка кэша = порча данных)
typedef struct MeBox {
  unsigned sent;                        // номер задания (главный)
  unsigned done;                        // номер сделанного (ME, последним)
  unsigned buf, words;                  // вход: кэшируемый адрес буфера, слов
  unsigned sum;                         // выход: meJobSum
  unsigned status;                      // выход: регистр Status ME (бит 29 — сопроцессор FPU доступен)
  unsigned fcsr0, fcsr1;                // выход: FCR31 ME до и после выключения ловушек (fpuguard.h, урок 252)
  unsigned beat;                        // сердцебиение: сколько заданий ME начал
  unsigned kind;                        // задание: ME_KIND_SUM (проба) или ME_KIND_MIX (правка 276: смешивание звука, viewer/mixdsp.h)
  unsigned job;                         // ME_KIND_MIX: кэшируемый адрес MixJob (ME сбрасывает свой кэш над ним до и после счёта); words — sizeof
  // очередь с приоритетом звука (облако 05.10, задача 6): за идущим заданием (частицы) главный «прицепляет» следующее (звук) —
  // ME посчитает его сразу после, а не отдаст главному процессору. Поля пишет главный ДО kick: next = took = chain = 0
  unsigned next;                        // главный: некэшируемый адрес ящика, прицепленного следом (0 — нет)
  unsigned took;                        // ME: какой ящик взял следом (0 — никакой)
  unsigned chain;                       // ME: ME_CH_CLOSED — своё сделано, «next» прочитан; | ME_CH_FIN — всё решено (последним)
  unsigned pad[2];                      // служба-пустышка (meprobe.c, схемы 1–3): адрес задания игры и «сделано»
} __attribute__((aligned(64))) MeBox;
#define ME_CH_CLOSED 1u
#define ME_CH_FIN 2u
#ifdef __cplusplus
static_assert(sizeof(MeBox) == 64, "MeBox — 64 байта");
#else
_Static_assert(sizeof(MeBox) == 64, "MeBox — 64 байта");
#endif

// Очередь «звук после частиц» — договор двух сторон (некэшируемая память, после каждой записи — sync).
//   ME (после своего задания, me_gametask.c): chain = CLOSED; n = next; если n — took = n, считает ящик n; chain |= FIN.
//   Главный (meChainAttach): next = мой; c = CLOSED? нет -> ME ещё не читал next и прочтёт его после записи CLOSED: прицеплено.
//   да -> ME мог прочесть next и до, и после — ждём took или FIN: взял мой — прицеплено, иначе — не прицеплено
//   (next обнуляем; ME уже свободен — обычный kick). Ни потери, ни двойного счёта (tests/me/chain_host.c — все порядки шагов).
#ifndef ME_CHAIN_OLD
#define ME_CHAIN_OLD 0                  // 1 — без очереди: ME занят — звук считает главный (как TEST 18)
#endif
static inline void meSync(void) {
#if defined(__psp__) || defined(__mips__)
  __asm__ volatile("sync" : : : "memory");
#else
  __atomic_thread_fence(__ATOMIC_SEQ_CST);
#ifdef ME_SYNC_HOOK
  ME_SYNC_HOOK();                       // tests/me/chain_host.c: здесь «ME» делает свои шаги между шагами главного
#endif
#endif
}
// главный: ящик «a» (уже заполнен, sent выставлен) — следом за идущим заданием ящика «run». -> 1 прицеплено, 0 — нет;
// wait(u) — пауза ожидания fin (мкс; на хосте — шаг ME)
static inline int meChainAttach(volatile MeBox *run, volatile MeBox *a, void (*wait)(unsigned us)) {
  if (ME_CHAIN_OLD || !run || (run->chain & ME_CH_FIN) || run->sent == 0 || run->took) return 0;   // took — уже взят прошлый (ABA)
  run->next = (unsigned)(unsigned long)a; meSync();
  if (!(run->chain & ME_CH_CLOSED)) return 1;
  for (int i = 0; i < 2000 && !(run->chain & ME_CH_FIN) && !run->took; i++) wait(1);   // ME в конце своего задания: решение за микросекунды
  if (run->took == (unsigned)(unsigned long)a) return 1;
  run->next = 0; meSync();
  return 0;
}
// Отправка задания клиента c (0 звук, 1 частицы) в ящик u (некэшируемый адрес, схема 0) — общая для службы (viewer/me/meprobe.c)
// и хост-гейта tests/me/queue_host.c (настоящие потоки). kick(u) — поставить ящик ME (ME_SVC_BUSY — ME занят), now — часы, мкс.
// run[c]/runT[c] — последний ящик клиента, отданный ME своим kick, и когда. -> номер задания (> 0) или ME_SVC_BUSY.
#define ME_SVC_BUSY (-1)               // kick/отправка: у ME другое задание (клиент считает сам)
#define ME_CHAIN_MAX_US 15000u          // к заданию старше не цепляемся — ME, видимо, завис (тайм-ауты: частицы 20 мс, звук 50 мс)
typedef struct MeQueue { volatile MeBox *run[2]; unsigned runT[2]; unsigned chained; } MeQueue;
static inline int meBoxSubmit(MeQueue *Q, int c, volatile MeBox *u, unsigned kind, unsigned job, unsigned words,
                              int (*kick)(volatile MeBox *), unsigned (*now)(void), void (*wait)(unsigned)) {
  c &= 1;
  if (u->sent != u->done) return ME_SVC_BUSY;                                  // своё прошлое задание не забрано
  if (!ME_CHAIN_OLD && Q->run[c] == u && !(u->chain & ME_CH_FIN)) return ME_SVC_BUSY;   // ME ещё в хвосте прошлого (прицепленный)
  u->kind = kind; u->job = job; u->words = words; u->sum = 0;
  u->next = 0; u->took = 0; u->chain = 0;
  unsigned q = u->sent + 1; if (!(q & 0x7fffffffu)) q = 1;
  u->sent = q; meSync();
  if (kick(u) != ME_SVC_BUSY) { Q->run[c] = u; Q->runT[c] = now(); return (int)q; }
  if (c == 0 && Q->run[1] && now() - Q->runT[1] < ME_CHAIN_MAX_US) {           // звук за частицами; этот ящик ME возьмёт сам — FIN
    u->chain = ME_CH_CLOSED | ME_CH_FIN; meSync();
    if (meChainAttach(Q->run[1], u, wait)) { Q->chained++; return (int)q; }
  }
  u->chain = ME_CH_CLOSED | ME_CH_FIN;                                         // ящик ME не получил: к нему не цепляться
  u->sent = u->done; meSync(); return ME_SVC_BUSY;                             // номер назад
}
// ME: шаги хвоста (разбиты для проверки порядков на хосте)
static inline unsigned meChainClose(volatile MeBox *b) { b->chain = ME_CH_CLOSED; meSync(); return b->next; }
static inline void meChainTake(volatile MeBox *b, unsigned n) { b->took = n; meSync(); }   // до счёта прицепленного: главный не ждёт
static inline void meChainFinish(volatile MeBox *b) { b->chain = ME_CH_CLOSED | ME_CH_FIN; meSync(); }
#define ME_KIND_SUM 0u
#define ME_KIND_SPATIAL 5u              // Standalone test: distance/pan batch, same integer DSP as mixer
#define ME_KIND_MIX 2u
#define ME_KIND_FX 4u                   // правка 313: частицы и свечение — шаг жизни частиц и сборка биллбордов (viewer/fxdsp.h fxJobRun)
#define ME_KIND_CITY 6u                 // №653: отсечение города (viewer/citycull.h ccRun), клиент 1 службы
#define ME_KIND_TINY 3u                 // TEST 10, лесенка: только сердцебиение, Status и «сделано» (как счётчик примера автора MIST)
#define ME_MIX_BADSIZE 0xbadb0bu        // MeBox.sum: размер MixJob у игры и модуля разный (сборки разные) — счёт не шёл

// ---------------------------------------------------------------------------------------------------------------------------
// Правка 313 (Роб 04.10: «делегируй Media Engine прозрачные элементы, свечение, музыку») — схема памяти заданий ME. Выбирается
// ОДНОЙ константой ME_MEM по итогам TEST 10 (лесенка, строки «ML N» в me.txt): где лежит ящик и каким адресом ME видит ящик,
// задание и данные игры (банк звуков, пакет частиц). Без флаг-файла meaudio / mefx рядом с EBOOT ME не трогается вовсе.
//   ME_MEM_USER  0 — как TEST 8: ящик в памяти игры, ME получает его некэшируемым адресом 0x4…; задание — по адресу игры (кэш ME
//                    сбрасывается вокруг счёта), банк звуков — 0x4… . Выбирать, если прошла ступень 9 (ящик в верхних 32 МБ)
//   ME_MEM_KBOX  1 — ящик в памяти ядра модуля, ME получает кэшируемый адрес ядра 0x88… и сам сбрасывает строку (ступень 3, как у
//                    автора MIST); задание и данные — память игры по обычному кэшируемому адресу, ME сбрасывает свой кэш (ступени 7 и 8)
//   ME_MEM_KBOXU 2 — то же, но ящик — некэшируемым адресом ядра 0xA8… (ступень 4: прошла 4, а 3 нет)
//   ME_MEM_KERN  3 — ящик и задание звука — в памяти ядра модуля, все адреса — кэшируемые адреса ядра 0x8… (ступени 3, 5–6);
//                    задание звука модуль переносит из памяти игры и обратно в режиме ядра (mixJobIn/mixJobOut, только звучащие
//                    голоса); данные игры ME читает через кэшируемый адрес ядра той же памяти (0x80000000 | физический адрес)
//   +ME_MEM_LOW  4 — прибавить, если ступень 8 (верхние 32 МБ) НЕ прошла: задание и данные обязаны лежать ниже 0x0A000000, иначе ME
//                    не включается («ME audio off: high …»), звук и частицы — на главном, как сейчас
// Для тура без пересборки содержимое флаг-файла (первый байт) может заменить схему: «u» 0, «b» 1, «c» 2, «k» 3; заглавная буква
// (U B C K) — то же с ME_MEM_LOW. «1» — схема ME_MEM этой сборки
#define ME_MEM_USER 0
#define ME_MEM_KBOX 1
#define ME_MEM_KBOXU 2
#define ME_MEM_KERN 3
#define ME_MEM_LOW 4
#ifndef ME_MEM
#define ME_MEM ME_MEM_USER              // 04.10 22:2x по TEST 13–16 на железе: ME не пускают в память ядра — ящик, задание и данные в памяти игры
#endif
#define ME_SCHEME_KBOX(s) (((s) & 3) != ME_MEM_USER)         // ящик в памяти ядра: главный читает его только через модуль
static inline int meSchemeFromChar(char c, int dflt) {
  switch (c) { case 'u': return 0; case 'b': return 1; case 'c': return 2; case 'k': return 3;
               case 'U': return 4; case 'B': return 5; case 'C': return 6; case 'K': return 7; }
  return dflt;
}
// адрес памяти игры (как его видит главный процессор) -> адрес, которым её читает ME в схеме s
static inline unsigned meUserAddr(int s, unsigned a) {
  return (s & 3) == ME_MEM_KERN ? (0x80000000u | (a & 0x1fffffffu)) : (a & 0x1fffffffu);
}
static inline int meIsHigh(unsigned a) { return (a & 0x1fffffffu) >= 0x0a000000u; }

// игра -> модуль: копия уходит в аргументы sceKernelStartModule; модуль пишет итог по адресу res (память игры)
typedef struct MeProbeArgs {
  unsigned magic, jobs, timeoutUs, res;
  char dir[192];                        // папка игры (с «/» в конце): туда шаги пробы — me.txt
} MeProbeArgs;

typedef struct MeProbeRes {
  unsigned magic;                       // ME_PROBE_MAGIC — модуль дошёл до записи итога
  int stage;                            // докуда дошла проба: 1 таблица, 2 запуск MIST, 3 ячейка, 4 задания, 5 уборка
  int table;                            // образ ядра ME по слову 0x88300018: 2 — t2img (Slim и новее, проба идёт), 3 — img (Phat, не идёт), <0 — чужой
  int init;                             // код meSafeKernelTaskMistInit / своей ячейки (0 — хорошо)
  int jobs, ok, sumOk, timeout, timeoutJob;
  unsigned rtMin, rtMax, rtSum;         // туда-обратно, мкс (часы главного процессора)
  unsigned status, fcsr0, fcsr1, beat;  // с ME (последнее задание)
  int evf;                              // сколько раз флаг ответа ME прошивки (SceMediaEngineRpcWait) от наших заданий снят ожиданием (до 2 мс)
  int evfFound;                         // флаг прошивки найден (1) — иначе evf не считается
  int evfPre, evfEnd, evfCleared;       // бит 0 флага до пробы (до перезапуска ME), в конце пробы (-1 — флага нет), снят ли в конце
  unsigned st0, st1;                    // слово состояния ME 0xbfc00700 до пробы и после заданий (до возврата)
  int mode;                             // 1 — mist, 2 — reset (запасной путь me-simple-count, не собран)
  unsigned msTotal;                     // вся проба, мс
} MeProbeRes;

// Правка 276 — режим службы: модуль ставит задачу в ячейку ME и остаётся; игра шлёт задания смешивания звука через функции
// модуля в режиме ядра (kubridge kuKernelCall): kick — запустить задание из ящика, quiesce — ME больше не трогаем (ролик, сон):
// снять флаг ответа ME прошивки, вернуть слово состояния ME. Шаги — строками «MEA …» в me.txt
// Правка 313: служба знает схему памяти (ME_MEM) и держит ящик в памяти ядра (схемы 1–3): тогда kick получает адрес задания игры,
// а poll отдаёт «сделано» (младшее слово) и итог задания (старшее) — главный ящик ядра сам не читает (режим пользователя)
#define ME_SVC_MAGIC 0x3253454du        // "MES2" (правка 313: поле scheme; прежний "MES1" — без него)
typedef struct MeSvcArgs { unsigned magic, res; int scheme; unsigned pad; char dir[192]; unsigned gameFn; } MeSvcArgs;   // gameFn — meGameTask игры (04.10)
typedef struct MeSvcRes {
  unsigned magic;                       // ME_SVC_MAGIC — служба поставлена
  int stage, table, init, evfFound, evfPre;
  unsigned st0, kick, quiesce;          // слово состояния ME до службы; адреса функций модуля (режим ядра)
  unsigned msTotal;
  unsigned poll;                        // правка 313: «сделано»/итог из ящика ядра (схемы 1–3)
  int scheme;                           // схема, которую служба приняла
  unsigned kbox, kjob;                  // ящик и задание звука в памяти ядра (0 — не нужны в этой схеме)
} MeSvcRes;
// Kernel module and caller run on the same CPU. The caller invalidates this line:
// publish the final signature AND entry points to RAM before module_start returns
static inline void meSvcPublish(MeSvcRes *r, void (*writeback)(const void *, unsigned int)) {
  r->magic = ME_SVC_MAGIC;
  meSync();
  writeback(r, sizeof *r);
  meSync();
}
// meSvcKick(a1, a2, a3): схема 0 — a1 = некэшируемый адрес ящика клиента (ящик заполнила игра); 1–3 — a1 = клиент (0 звук,
// 1 частицы) | вид задания << 8, a2 = адрес задания в памяти игры, a3 = его размер. -> номер задания или <0: у ME ещё прошлое
// задание (ME_SVC_BUSY — клиент считает сам), не тот размер (-2). meSvcPoll(клиент) -> «сделано» (биты 0–30), бит 31 — не посчитано
#define ME_POLL_BAD 0x80000000u

// TEST 10 (04.10, Роб: «ещё больше проверяем возможности и Media Engine… тест очень медленный, постепенно пробивай всё») — лесенка:
// модуль грузится один раз (ступень 0, только чтение), дальше игра зовёт ступени по одной через kuKernelCall(step, n) с паузами
// и проверочным роликом между ними. Ступени (viewer/me/sharme.c meLadderStep): 1 перезапуск MIST, 2 своя функция в ячейку 13,
// 3 пустое задание, ящик — кэшируемый адрес ядра (как у автора), 4 то же через некэшируемый адрес ядра, 5 сумма 16 КБ из памяти
// ядра, 6 то же ×200 (время), 7 сумма из нижней памяти игры (< 0x0A000000), 8 сумма из верхних 32 МБ (≥ 0x0A000000),
// 9 пустое задание с ящиком в верхних 32 МБ (как TEST 8 — последним), 99 уборка. Ступень без ответа — «stuck»: дальше ME не трогаем
#define ME_LADDER_MAGIC 0x314c454du     // "MEL1"
#define ME_LADDER_BYTES 16384           // буфер задания «сумма»
typedef struct MeLadderArgs { unsigned magic, res, lowBuf, lowBytes; char dir[192]; unsigned gameFn; } MeLadderArgs;   // gameFn — TEST 15: meGameTask игры
typedef struct MeLadderRes {
  unsigned magic;                       // ME_LADDER_MAGIC — ступень 0 прошла, step — адрес функции ступеней (режим ядра)
  unsigned step;
  int stuck;                            // 1 — ME не ответил на ступени: дальше ME и роликов не трогаем
  int last;                             // код последней ступени
  unsigned pad[4];
  char line[224];                       // строка последней ступени (как в me.txt)
} __attribute__((aligned(64))) MeLadderRes;

// Задание: свёртка слов буфера (FNV-1a по 32-битным словам: s = (s ^ w) · 16777619) — чувствительна к порядку слов и к любой
// устаревшей строке кэша (одно умножение и одно «исключающее или» на слово: на ME и на главном — одинаково, только целые)
static inline unsigned meJobSum(const unsigned *p, unsigned n) {
  unsigned s = 0x811c9dc5u;
  for (unsigned i = 0; i < n; i++) s = (s ^ p[i]) * 16777619u;
  return s;
}
// Узор задания k: слова-«шум» (перемешивание как в конце хеша murmur3), у каждого задания свой — устаревшая строка кэша
// от прошлого задания даёт другую сумму
static inline unsigned meJobWord(unsigned k, unsigned i) {
  unsigned x = i * 0x9e3779b9u + k * 0x85ebca6bu;
  x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
  return x;
}

#endif
