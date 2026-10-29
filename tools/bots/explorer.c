// Каскадёр и пешеход (пункт Б3, docs/БОТЫ-ИГРОКИ_2026-09-28.md §3.4–3.5): исследователь в духе Go-Explore на игре без экрана.
// Архив ячеек (x, z по 6 м; y по 2 м; скорость 3 корзины; земля/воздух; пешком/в машине): первый снимок мира в ячейке и цепочка
// «родитель + макрос». Цикл: ячейка с весом ~1/√(посещений+1) -> снимок -> макрос 2–5 с -> новые ячейки в архив. Мир не
// сбрасывается: продолжаем из редких мест. Старты — спавн уровня и точки дорог (естественное; стресс-стартов здесь нет).
// Цели — из данных (tools/bots/targets.py): крыши (стоять на площадке), трамплины (кромка на скорости), стёкла Krusty (разбито),
// монеты (подобрана), осы и карточки (добрался). Повтор цели: старт + цепочка макросов -> ввод по кадрам (.in для game_headless).
//   explorer LEVEL HOMER ROADS TARGETS --secs S [--seed N] [--cells 20000] [--out DIR] [--routes routes-l1.tsv] [--plant-sky]
//   --routes: ещё старты — начало разгона на каждый трамплин (пункт 10), курсом на кромку; макрос «разгон прямо» 4–8 с
//   --max-macros N: стоп по числу макросов (не по часам) — прогон повторяется побайтно: A/B прежнего и нового кода на тех же seed (правка 339)
//   --plant-sky: контроль гейта — подложить крышу 10×10 м на 40 м прямо над спавном (там нет опоры), её не должно достигаться;
//                сборка с -DEXP_BREAK_ROOF=1 (крыша без проверки высоты и опоры) обязана её «достичь» — гейт красный
// События пешехода и машины (кластер = вид + клетка 8 м + слой опоры + объект коллизии, Т1.1; повтор — первый найденный случай): foot_trapped — Гомер заперт: бег 1 с
// на полном стике не сдвинул его, проба из снимка (8 сторон × 1 с бега и столько же с двойным прыжком) нигде не дала 1.5 м и △ за 3 с не посадил в машину; fall — ниже
// самой низкой точки коллизии уровня на 5 м (ушёл за край земли или сквозь неё). Строки "E\t...".
//   --cells-out DIR: анатомия уровня (Роб 04.10, tools/bots/cellsout.h) — все места бота в DIR/cells.tsv (x, z по 6 м; y по 2 м; режим;
//                опора; посещений; первое время; курс машины), переходы по земле DIR/edges.tsv, каждое событие с координатами
//                DIR/events.tsv; плюс car_trapped — машина не выезжает: на газу 1 с стоит на месте, проба из снимка (8 заходов по 2.5 с:
//                газ прямо/влево/вправо, назад прямо/влево/вправо, назад и газ с рулём в обе стороны) нигде не дала 3 м. Без ключа
//                поведение и вывод прежние
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "navgraph.h"
#include "cellsout.h"

// ------------------------------------------------------------------ цели
typedef struct { char kind[8], name[40]; float x, y, z, r, x0, z0, x1, z1; int reached, cell, frame, mk, ma, mb, mfr; float t;
  float bd, bh, bx, by, bz; int bfoot; } Target;   // лучший подход недостигнутой цели: по плоскости до цели/площадки, нехватка высоты, где   // cell — ячейка, из которой начат макрос, где цель достигнута
static Target *tg; static int ntg;
#define TG 16.f
static int *tgStart, *tgList, tgW, tgH; static float tgOx, tgOz;
static void loadTargets(const char *path, int plantSky) {
  FILE *f = fopen(path, "r"); if (!f) { fprintf(stderr, "explorer: нет %s\n", path); exit(2); }
  tg = calloc(1024, sizeof(Target)); char ln[256];
  while (fgets(ln, sizeof ln, f) && ntg < 1023) {
    Target *t = &tg[ntg];
    if (sscanf(ln, "%7s %39s %f %f %f %f %f %f %f %f", t->kind, t->name, &t->x, &t->y, &t->z, &t->r, &t->x0, &t->z0, &t->x1, &t->z1) == 10) { t->cell = -1; t->bd = 1e9f; ntg++; }
  }
  fclose(f);
  if (plantSky) { float sx, sy, sz, sh; bwSpawn(&sx, &sy, &sz, &sh);
    // прямо над стартом со спавна (28.09): сломанная проверка обязана сработать сразу, не завися от того, куда уедет разведка
    Target t = {"roof", "planted_roof", sx, sy + 40.f, sz, 2.f, sx - 5.f, sz - 5.f, sx + 5.f, sz + 5.f, 0, -1, 0, 0, 0, 0, 0, 0}; tg[ntg++] = t; }
  const ColWorld *cw = bwCol(); tgOx = cw->ox; tgOz = cw->oz; tgW = (int)(cw->W * cw->cell / TG) + 2; tgH = (int)(cw->H * cw->cell / TG) + 2;
  tgStart = calloc((size_t)tgW * tgH + 1, sizeof(int)); tgList = malloc(sizeof(int) * (size_t)ntg * 9 + 1);
  for (int pass = 0; pass < 2; pass++) {
    for (int i = 0; i < ntg; i++) {
      Target *t = &tg[i]; float rx = t->r, rz = t->r, cx = t->x, cz = t->z;
      if (!strcmp(t->kind, "roof")) { rx = (t->x1 - t->x0) * .5f; rz = (t->z1 - t->z0) * .5f; cx = (t->x0 + t->x1) * .5f; cz = (t->z0 + t->z1) * .5f; }
      int gx0 = (int)((cx - rx - tgOx) / TG), gx1 = (int)((cx + rx - tgOx) / TG), gz0 = (int)((cz - rz - tgOz) / TG), gz1 = (int)((cz + rz - tgOz) / TG);
      for (int gz = gz0; gz <= gz1; gz++) for (int gx = gx0; gx <= gx1; gx++) {
        if (gx < 0 || gz < 0 || gx >= tgW || gz >= tgH) continue;
        int c = gz * tgW + gx; if (pass == 0) tgStart[c + 1]++; else tgList[tgStart[c]++] = i;
      }
    }
    if (pass == 0) { for (int c = 0; c < tgW * tgH; c++) tgStart[c + 1] += tgStart[c]; tgList = realloc(tgList, sizeof(int) * (size_t)(tgStart[tgW * tgH] + 1)); }
    else { for (int c = tgW * tgH; c > 0; c--) tgStart[c] = tgStart[c - 1]; tgStart[0] = 0; }
  }
}

// ------------------------------------------------------------------ разностные снимки: мир + изменённые блоки массивов модулей
// относительно начального снимка (пропы, монеты, стейтпропы почти всегда те же) — 40 КБ вместо 164 на ячейку
typedef struct { BotWorld w; uint16_t *idx; unsigned char *blk; int nblk; } DSnap;
static BotSnap S0, Stmp;
#define DB 64
static void dsave(const BotWorld *w, DSnap *d) {
  bwSave(w, &Stmp); d->w = Stmp.w;
  const unsigned char *A[5] = {(void *)Stmp.pst, (void *)Stmp.coin, Stmp.spmem, Stmp.collmem, Stmp.trmem}, *B[5] = {(void *)S0.pst, (void *)S0.coin, S0.spmem, S0.collmem, S0.trmem};
  size_t N[5] = {Stmp.npst * sizeof(PropState), Stmp.ncoin * sizeof(Coin), Stmp.nspmem, Stmp.ncollmem, Stmp.ntrmem}; int n = 0; static uint16_t ix[8192]; static unsigned char bk[8192 * DB];
  for (int a = 0; a < 5; a++) for (size_t o = 0; o < N[a]; o += DB) { size_t l = N[a] - o < DB ? N[a] - o : DB;
    if (memcmp(A[a] + o, B[a] + o, l)) { if (n >= 8192) { fprintf(stderr, "explorer: снимок больше 8192 блоков\n"); exit(3); } ix[n] = (uint16_t)(a << 13 | (o / DB)); memcpy(bk + (size_t)n * DB, A[a] + o, l); n++; } }
  d->nblk = n; d->idx = malloc(sizeof(uint16_t) * (size_t)(n + 1)); d->blk = malloc((size_t)n * DB + 1);
  memcpy(d->idx, ix, sizeof(uint16_t) * (size_t)n); memcpy(d->blk, bk, (size_t)n * DB);
}
static void dload(BotWorld *w, const DSnap *d) {
  Stmp.w = d->w; memcpy(Stmp.pst, S0.pst, Stmp.npst * sizeof(PropState)); memcpy(Stmp.coin, S0.coin, Stmp.ncoin * sizeof(Coin)); memcpy(Stmp.spmem, S0.spmem, Stmp.nspmem);
  memcpy(Stmp.collmem, S0.collmem, Stmp.ncollmem); memcpy(Stmp.trmem, S0.trmem, Stmp.ntrmem);
  unsigned char *A[5] = {(void *)Stmp.pst, (void *)Stmp.coin, Stmp.spmem, Stmp.collmem, Stmp.trmem};
  size_t N[5] = {Stmp.npst * sizeof(PropState), Stmp.ncoin * sizeof(Coin), Stmp.nspmem, Stmp.ncollmem, Stmp.ntrmem};
  for (int k = 0; k < d->nblk; k++) { int a = d->idx[k] >> 13; size_t o = (size_t)(d->idx[k] & 8191) * DB, l = N[a] - o < DB ? N[a] - o : DB; memcpy(A[a] + o, d->blk + (size_t)k * DB, l); }
  bwLoad(w, &Stmp);
}

// ------------------------------------------------------------------ архив ячеек
typedef struct { uint32_t key; int parent, slot, visits, depth; uint8_t kind, foot; int8_t a, b; uint16_t frames; uint32_t seed; float near; } Cell;   // near — близость к недостигнутой цели 0..1
static Cell *cells; static int ncell, cap = 20000; static DSnap *snaps;
#define HS (1 << 17)
static int hsh[HS];
static uint32_t cellKey(const BotWorld *w) {
  int foot = gameOnFoot(&w->G); float x = foot ? w->homer.x : w->car.x, y = foot ? w->homer.y : w->car.y, z = foot ? w->homer.z : w->car.z;
  float v = foot ? w->homer.speed : fabsf(w->car.v); int sb = v < 8.f ? 0 : v < 18.f ? 1 : 2, gr = foot ? w->homer.grounded : w->car.grounded;
  uint32_t k = (uint32_t)((int)floorf(x / 6.f) & 1023) | (uint32_t)((int)floorf(z / 6.f) & 1023) << 10 | (uint32_t)((int)floorf(y / 2.f) & 127) << 20;
  return k | (uint32_t)sb << 27 | (uint32_t)gr << 29 | (uint32_t)foot << 30 | 1u << 31;
}
static int findCell(uint32_t k) { for (uint32_t h = (k * 2654435761u) >> 15 & (HS - 1); hsh[h]; h = (h + 1) & (HS - 1)) if (cells[hsh[h] - 1].key == k) return hsh[h] - 1; return -1; }
static void addHash(uint32_t k, int i) { uint32_t h = (k * 2654435761u) >> 15 & (HS - 1); while (hsh[h]) h = (h + 1) & (HS - 1); hsh[h] = i + 1; }

// ------------------------------------------------------------------ макросы: ввод — чистая функция параметров и номера кадра
static BotWorld W; static uint32_t rs = 1; static int verifyN;
static uint32_t xr(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs; }
enum { M_GAS, M_TURN, M_DRIFT, M_BRAKE, M_SPIN, M_WALK, M_JUMP, M_ENTER, M_RUNUP, M_COUNT };
static void macroInput(int kind, int a, int b, int f, int frames, unsigned *bt, float *ax, float *ay) {
  float s = a / 100.f; *bt = 0; *ax = 0; *ay = 0; (void)frames;
  switch (kind) {
    case M_GAS: *bt = GP_R; *ax = s * .3f; break;                                   // газ почти прямо
    case M_TURN: *bt = GP_R; *ax = s; break;                                        // газ + руль
    case M_DRIFT: *bt = GP_R | (f > 20 ? GP_SQUARE : 0); *ax = s > 0 ? 1.f : -1.f; break;   // ручник-занос
    case M_BRAKE: *bt = GP_L; *ax = s; break;                                       // тормоз / назад с рулём
    case M_SPIN: *bt = f < 60 ? GP_L : GP_R; *ax = f < 60 ? s : -s; break;          // назад с рулём, потом газ
    case M_WALK: if (f == 0) *bt = GP_TRIANGLE; else { *bt = GP_CIRCLE; *ax = cosf(b * .0245f) * .99f; *ay = -sinf(b * .0245f) * .99f; if (f % 50 == 25 && a > 0) *bt |= GP_CROSS; } break;   // выйти, бег (○ зажат) с прыжками
    case M_JUMP: if (f == 0) *bt = GP_TRIANGLE; else { *bt = GP_CIRCLE; *ax = cosf(b * .0245f); *ay = -sinf(b * .0245f); if (f % 40 == 5 || f % 40 == 15) *bt |= GP_CROSS; } break;   // двойной прыжок с разбега (○)
    case M_RUNUP: *bt = GP_R; *ax = s * .05f; break;                                // разгон строго прямо (заезд на трамплин)
    default: if (f == 0) *bt = GP_TRIANGLE; else { *bt = GP_R; *ax = s; } break;   // сесть в машину и газ
  }
}
static int footMacro(int kind) { return kind == M_WALK || kind == M_JUMP; }

// ------------------------------------------------------------------ проверка целей в кадре
static float tSim; static int mK, mA, mB, mFr;   // текущий макрос (для повтора цели)
static void checkTargets(int cellIdx, int frame) {
  int foot = gameOnFoot(&W.G); float x = foot ? W.homer.x : W.car.x, y = foot ? W.homer.y : W.car.y, z = foot ? W.homer.z : W.car.z;
  int gx = (int)((x - tgOx) / TG), gz = (int)((z - tgOz) / TG); if (gx < 0 || gz < 0 || gx >= tgW || gz >= tgH) return;
  int c = gz * tgW + gx;
  for (int k = tgStart[c]; k < tgStart[c + 1]; k++) {
    Target *t = &tg[tgList[k]]; if (t->reached) continue;
    int hit = 0;
#if EXP_BREAK_ROOF
    if (!strcmp(t->kind, "roof")) hit = x >= t->x0 && x <= t->x1 && z >= t->z0 && z <= t->z1;   // сломано нарочно: без высоты и опоры
#else
    if (!strcmp(t->kind, "roof")) hit = x >= t->x0 && x <= t->x1 && z >= t->z0 && z <= t->z1 && y >= t->y - .5f && y <= t->y + 3.f && (foot ? W.homer.grounded : W.car.grounded);
#endif
    else if (!strcmp(t->kind, "ramp")) hit = !foot && hypotf(x - t->x, z - t->z) < t->r && fabsf(y - t->y) < 2.f && fabsf(W.car.v) > 6.f;
    else if (!strcmp(t->kind, "coin")) { int i = atoi(t->name + 4); hit = W.haveCoins && i < (int)W.coins.nworld && !W.coins.c[i].active; }
    else if (!strcmp(t->kind, "glass")) { int i = atoi(t->name + 5); hit = W.haveProps && i < (int)W.props.ninst && W.props.st[i].hidden; }
    else hit = hypotf(x - t->x, z - t->z) < t->r && fabsf(y - t->y) < 2.5f;   // осы, карточки, небо
    if (hit) { t->reached = 1; t->cell = cellIdx; t->frame = frame; t->t = tSim; t->mk = mK; t->ma = mA; t->mb = mB; t->mfr = mFr; }
    else if (!strcmp(t->kind, "roof") || !strcmp(t->kind, "wasp") || !strcmp(t->kind, "card") || !strcmp(t->kind, "ramp")) {
      // подход: до площадки крыши (0 внутри) или до точки цели; нехватка высоты считается только у крыш и целей выше игрока
      float dx = 0, dz = 0;
      if (!strcmp(t->kind, "roof")) { dx = x < t->x0 ? t->x0 - x : x > t->x1 ? x - t->x1 : 0; dz = z < t->z0 ? t->z0 - z : z > t->z1 ? z - t->z1 : 0; }
      else { dx = x - t->x; dz = z - t->z; }
      float d = hypotf(dx, dz), h = t->y - .5f - y; if (h < 0) h = 0;
      if (d + 2.f * h < t->bd + 2.f * t->bh || t->bd > 1e8f) { t->bd = d; t->bh = h; t->bx = x; t->by = y; t->bz = z; t->bfoot = foot; }
    }
  }
}

// ------------------------------------------------------------------ события: кластеры (клетка 8 м + вид), первый случай — повтор
typedef struct { int kind, gx, gz, n, cell, frame, mk, ma, mb, mfr; float x, y, z, t; int layer; char obj[16]; } Event;
enum { EV_FOOT_TRAPPED, EV_FALL, EV_CAR_TRAPPED, EV_COUNT };
static const char *evName[EV_COUNT] = {"foot_trapped", "fall", "car_trapped"};   // car_trapped — только с --cells-out
static Event ev[4096]; static int nev; static float minY = 1e9f;
// Т1.1: ключ = вид + клетка 8 м + слой опоры + объект (bwWhere); где — точка, от которой считать слой (для провала — последняя опора)
static void addEvent(int kind, float x, float y, float z, int cellIdx, int frame, const float where[3]) {
  int gx = (int)floorf(x / 8.f), gz = (int)floorf(z / 8.f), nl; char obj[16];
  int layer = bwWhere(where[0], where[1], where[2], 1.2f, &nl, obj);
  coEvent(evName[kind], x, y, z, layer, obj, gameOnFoot(&W.G));   // --cells-out: каждое событие, не только первое в кластере
  for (int i = 0; i < nev; i++) if (ev[i].kind == kind && ev[i].gx == gx && ev[i].gz == gz && ev[i].layer == layer && !strcmp(ev[i].obj, obj)) { ev[i].n++; return; }
  if (nev < 4096) { ev[nev] = (Event){kind, gx, gz, 1, cellIdx, frame, mK, mA, mB, mFr, x, y, z, tSim, layer, ""}; snprintf(ev[nev].obj, 16, "%s", obj); nev++; }
}

// Гомер заперт? проба из снимка: 8 сторон × 60 кадров бега с двойным прыжком; мир после пробы — тот же (bwLoad)
static BotSnap Pb; static int probeN;
#define PH (1 << 14)
static uint32_t probedKey[PH]; static uint8_t probedCnt[PH];
static int trapped(float x, float z) {
  uint32_t key = (uint32_t)((int)floorf(x / 8.f) & 0xffff) | (uint32_t)((int)floorf(z / 8.f) & 0xffff) << 16, h = (key * 2654435761u) >> 18 & (PH - 1);
  while (probedKey[h] && probedKey[h] != (key | 1u << 31)) h = (h + 1) & (PH - 1);
  if (probedCnt[h] >= 2) return 0;   // клетка дважды проверена и свободна
  probedKey[h] = key | 1u << 31;
  bwSave(&W, &Pb); float x0 = W.homer.x, z0 = W.homer.z; int freeDir = 0; probeN++;
  for (int d = 0; d < 16 && !freeDir; d++) {   // 8 сторон бегом и 8 — бегом с двойным прыжком (прыжок с места гасит ход: только им — ложное «заперт», Т1.4)
    bwLoad(&W, &Pb); float a = (d & 7) * .785398f; int jump = d >= 8;
    for (int f = 0; f < 60; f++) bwStep(&W, GP_CIRCLE | (jump && (f == 5 || f == 15) ? GP_CROSS : 0), cosf(a), -sinf(a));   // бегом: ○ зажат
    if (!gameOnFoot(&W.G) || W.homer.state != HS_FOOT || hypotf(W.homer.x - x0, W.homer.z - z0) > 1.5f) freeDir = 1;   // сел в машину или ушёл — не заперт
  }
  if (!freeDir) {   // 9-я проба (Т1.4): △ — сесть в свою машину; сел за 3 с — не заперт (игрок уедет; зажат машиной у стены — не тупик)
    bwLoad(&W, &Pb); for (int f = 0; f < 180; f++) bwStep(&W, f == 5 ? GP_TRIANGLE : 0, 0.f, 0.f);
    if (!gameOnFoot(&W.G)) freeDir = 1;
  }
  bwLoad(&W, &Pb);
  if (freeDir) probedCnt[h]++;
  return !freeDir;
}

// машина заперта? (--cells-out) проба из снимка: 8 заходов по 150 кадров — газ прямо/влево/вправо, назад прямо/влево/вправо,
// назад 0.75 с и газ с рулём влево/вправо; хоть один отъехал на 3 м — не заперта. Мир после пробы — тот же (bwLoad)
static uint32_t carProbedKey[PH]; static uint8_t carProbedCnt[PH]; static int carProbeN;
static int carTrapped(float x, float z) {
  uint32_t key = (uint32_t)((int)floorf(x / 8.f) & 0xffff) | (uint32_t)((int)floorf(z / 8.f) & 0xffff) << 16, h = (key * 2654435761u) >> 18 & (PH - 1);
  while (carProbedKey[h] && carProbedKey[h] != (key | 1u << 31)) h = (h + 1) & (PH - 1);
  if (carProbedCnt[h] >= 2) return 0;   // клетка дважды проверена и свободна
  carProbedKey[h] = key | 1u << 31;
  bwSave(&W, &Pb); float x0 = W.car.x, z0 = W.car.z; int freeDir = 0; carProbeN++;
  static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
  for (int d = 0; d < 8 && !freeDir; d++) {
    bwLoad(&W, &Pb);
    for (int f = 0; f < 150; f++) { unsigned bt = d < 3 ? GP_R : d < 6 ? GP_L : (f < 45 ? GP_L : GP_R); float ax = d >= 6 && f < 45 ? -steer[d] : steer[d];
      bwStep(&W, bt, ax, 0.f); }
    if (gameOnFoot(&W.G) || W.car.destroyed || hypotf(W.car.x - x0, W.car.z - z0) > 3.f) freeDir = 1;   // разбита в пробе — не тупик места
  }
  bwLoad(&W, &Pb);
  if (freeDir) carProbedCnt[h]++;
  return !freeDir;
}

// близость к ближайшей недостигнутой цели (в 60 м по плоскости, с учётом высоты): тяга исследователя, не телепорт
static float nearness(void) {
  int foot = gameOnFoot(&W.G); float x = foot ? W.homer.x : W.car.x, y = foot ? W.homer.y : W.car.y, z = foot ? W.homer.z : W.car.z, best = 0;
  for (int i = 0; i < ntg; i++) { const Target *t = &tg[i]; if (t->reached || !strcmp(t->kind, "coin") || !strcmp(t->kind, "sky")) continue;
    float d = hypotf(t->x - x, t->z - z) + 2.f * fabsf(t->y - y); if (d < 60.f && 1.f - d / 60.f > best) best = 1.f - d / 60.f; }
  return best;
}

// ------------------------------------------------------------------ повтор: старт + цепочка макросов -> кадры
typedef struct { float x, y, z, h; } Start;
static Start starts[64]; static int nstarts;
// ввод по кадрам -> строки "N кнопки ax ay" (одинаковые кадры подряд — одной строкой)
static unsigned rlB; static float rlX, rlY; static int rlN;
static void rlPut(FILE *f, unsigned b, float ax, float ay) {
  if (rlN && b == rlB && ax == rlX && ay == rlY) { rlN++; return; }
  if (rlN) fprintf(f, "%d %x %.9g %.9g\n", rlN, rlB, rlX, rlY);
  rlB = b; rlX = ax; rlY = ay; rlN = 1;
}
static void rlEnd(FILE *f) { if (rlN) fprintf(f, "%d %x %.9g %.9g\n", rlN, rlB, rlX, rlY); rlN = 0; }
// ячейки от корня до cell, потом макрос (mk, ma, mb, mfr) до кадра frame включительно
static void writeChain(const char *out, const char *file, const char *what, float tsec, int cell, int mk, int ma, int mb, int mfr, int frame) {
  int chain[4096], n = 0; for (int c = cell; c >= 0 && n < 4096; c = cells[c].parent) chain[n++] = c;
  const Start *s = &starts[cells[chain[n - 1]].seed];
  char fn[512]; snprintf(fn, sizeof fn, "%s/%s.in", out, file); FILE *f = fopen(fn, "w"); if (!f) return;
  fprintf(f, "# explorer: %s за %.1f с игры; повтор: game_headless LEVEL HOMER --start %.9g %.9g %.9g %.9g --input этот_файл\n",
          what, tsec, s->x, s->y, s->z, s->h);
  fprintf(f, "30 0 0 0\n");
  for (int k = n - 2; k >= 0; k--) { const Cell *C = &cells[chain[k]];
    for (int fr = 0; fr < C->frames; fr++) { unsigned b; float ax, ay; macroInput(C->kind, C->a, C->b + 128, fr, C->frames, &b, &ax, &ay); rlPut(f, b, ax, ay); } }
  for (int fr = 0; fr <= frame; fr++) { unsigned b; float ax, ay; macroInput(mk, ma, mb, fr, mfr, &b, &ax, &ay); rlPut(f, b, ax, ay); }
  rlEnd(f); fclose(f);
}
static void writeRepro(const char *out, const Target *t) {
  char what[96]; snprintf(what, sizeof what, "цель %s %s", t->kind, t->name);
  writeChain(out, t->name, what, t->t, t->cell, t->mk, t->ma, t->mb, t->mfr, t->frame);
}

int main(int argc, char **argv) {
  if (argc < 5) { fprintf(stderr, "usage: explorer LEVEL HOMER ROADS TARGETS --secs S [--seed N] [--cells N] [--out DIR] [--plant-sky]\n"); return 2; }
  if (bwData(argv[1], argv[2], 0)) { fprintf(stderr, "explorer: нет данных\n"); return 2; }
  navLoad(argv[3]);
  float secs = 60; const char *out = 0, *routesPath = 0; int plant = 0; long maxMacros = 0;
  for (int i = 5; i < argc; i++) {
    if (!strcmp(argv[i], "--secs") && i + 1 < argc) secs = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--seed") && i + 1 < argc) rs = (uint32_t)strtoul(argv[++i], 0, 10) | 1;
    else if (!strcmp(argv[i], "--cells") && i + 1 < argc) cap = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
    else if (!strcmp(argv[i], "--plant-sky")) plant = 1;
    else if (!strcmp(argv[i], "--verify") && i + 1 < argc) verifyN = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--routes") && i + 1 < argc) routesPath = argv[++i];
    else if (!strcmp(argv[i], "--cells-out") && i + 1 < argc) coInit(argv[++i]);
    else if (!strcmp(argv[i], "--max-macros") && i + 1 < argc) maxMacros = atol(argv[++i]);   // правка 339: стоп по числу макросов — прогон повторяется побайтно (A/B старый/новый код)
  }
  loadTargets(argv[4], plant);
  { const ColWorld *cw = bwCol(); for (uint32_t i = 0; i < cw->ntri; i++) { const ColTri *T = &cw->tri[i];
      float m = fminf(T->a[1], fminf(T->b[1], T->c[1])); if (m < minY) minY = m; } }
  cells = calloc((size_t)cap, sizeof(Cell)); snaps = calloc((size_t)cap, sizeof(DSnap));
  bwNew(&W); bwSaveAlloc(&W, &S0); bwSaveAlloc(&W, &Stmp); bwSaveAlloc(&W, &Pb); bwSave(&W, &S0);   // начальный мир — база разностей
  // старты: спавн и 15 точек дорог (узлы графа), курс вдоль дороги — естественные
  float sx, sy, sz, sh; bwSpawn(&sx, &sy, &sz, &sh); starts[nstarts++] = (Start){sx, sy, sz, sh};
  for (int k = 0; k < 15 && nnode; k++) { int i = (int)(xr() % (unsigned)nnode), j = adjStart[i] < adjStart[i + 1] ? adj[adjStart[i]] : i;
    starts[nstarts++] = (Start){node[i].x, node[i].y, node[i].z, atan2f(node[j].x - node[i].x, node[j].z - node[i].z)}; }
  if (routesPath) {   // разгон на трамплины (build/sandbox/routes-l1.tsv, пункт 10): старт на дороге курсом на кромку
    FILE *rf = fopen(routesPath, "r"); char nm[64]; float x, y, z, dx, dz, lx, ly, lz; int gl;
    while (rf && nstarts < 64 && fscanf(rf, "%63s %f %f %f %f %f %f %f %f %d", nm, &x, &y, &z, &dx, &dz, &lx, &ly, &lz, &gl) == 10) starts[nstarts++] = (Start){x, y, z, atan2f(dx, dz)};
    if (rf) fclose(rf);
  }
  for (int s = 0; s < nstarts && ncell < cap; s++) {
    bwLoad(&W, &S0); bwPlace(&W, starts[s].x, starts[s].y, starts[s].z, starts[s].h);   // тот же мир (адреса массивов), что у снимков
    for (int k = 0; k < 30; k++) bwStep(&W, 0, 0, 0);
    coBreak(); coSampleWorld(&W, 0);
    uint32_t key = cellKey(&W); if (findCell(key) >= 0) continue;
    Cell *C = &cells[ncell]; *C = (Cell){key, -1, ncell, 0, 30, 0, 0, 0, 0, 0, (uint32_t)s};   // корень: seed = номер старта
    dsave(&W, &snaps[ncell]); addHash(key, ncell); ncell++;
  }
  clock_t t0 = clock(); long macros = 0, frames = 0;
  while ((clock() - t0) / (double)CLOCKS_PER_SEC < secs && (!maxMacros || macros < maxMacros)) {
    int best = -1; float bs = -1;   // турнир: 32 случайных ячейки, реже посещённая
    for (int k = 0; k < 32; k++) { int i = (int)(xr() % (unsigned)ncell); float sc = 1.f / sqrtf(cells[i].visits + 1.f) + .5f * cells[i].near + (xr() % 1000) * 1e-6f; if (sc > bs) { bs = sc; best = i; } }
    cells[best].visits++; dload(&W, &snaps[best]); coBreak(); coTick();
    int foot = gameOnFoot(&W.G), kind;
    do kind = (int)(xr() % M_COUNT); while ((foot && !footMacro(kind) && kind != M_ENTER) || (!foot && kind == M_ENTER));
    int a = (int)(xr() % 201) - 100, b = (int)(xr() % 256), fr = kind == M_RUNUP ? 240 + (int)(xr() % 241) : 120 + (int)(xr() % 181);
    tSim = cells[best].depth / 60.f; mK = kind; mA = a; mB = b; mFr = fr;
    float hx = 0, hz = 0;   // Гомер 1 с назад (для foot_stuck)
    float cx1 = W.car.x, cz1 = W.car.z;   // машина 1 с назад (car_trapped, --cells-out)
    float lg[3] = {foot ? W.homer.x : W.car.x, foot ? W.homer.y : W.car.y, foot ? W.homer.z : W.car.z};   // последняя точка на опоре (слой провала — откуда упал)
    for (int f = 0; f < fr; f++) {
      unsigned bt; float ax, ay; macroInput(kind, a, b, f, fr, &bt, &ax, &ay); bwStep(&W, bt, ax, ay); frames++; tSim += BW_DT;
      checkTargets(best, f);
      int ft = gameOnFoot(&W.G); float px = ft ? W.homer.x : W.car.x, py = ft ? W.homer.y : W.car.y, pz = ft ? W.homer.z : W.car.z;
      if (coOn && (f & 3) == 3) coSampleWorld(&W, frames);
      if (py < minY - 5.f) { addEvent(EV_FALL, px, py, pz, best, f, lg); break; }   // провал: дальше этот макрос не ведём
      if (ft ? W.homer.grounded : W.car.grounded) { lg[0] = px; lg[1] = py; lg[2] = pz; }
      if (ft && footMacro(kind) && f % 60 == 0) {
        if (f >= 120 && W.homer.grounded && W.homer.state == HS_FOOT && hypotf(px - hx, pz - hz) < .4f && trapped(px, pz)) { float here[3] = {px, py, pz}; addEvent(EV_FOOT_TRAPPED, px, py, pz, best, f, here); }
        hx = px; hz = pz;
      }
      if (coOn && !ft && f % 60 == 0 && (kind == M_GAS || kind == M_TURN || kind == M_DRIFT || kind == M_RUNUP)) {   // на газу 1 с на месте
        if (f >= 120 && W.car.grounded && !W.car.destroyed && hypotf(px - cx1, pz - cz1) < .4f && carTrapped(px, pz)) { float here[3] = {px, py, pz}; addEvent(EV_CAR_TRAPPED, px, py, pz, best, f, here); }
        cx1 = px; cz1 = pz;
      }
      if ((f % 15 == 14 || f == fr - 1) && ncell < cap) {   // новая ячейка: префикс этого макроса из best
        uint32_t key = cellKey(&W);
        if (findCell(key) < 0) {
          Cell *C = &cells[ncell]; *C = (Cell){key, best, ncell, 0, cells[best].depth + f + 1, (uint8_t)kind, (uint8_t)gameOnFoot(&W.G), (int8_t)a, (int8_t)(b - 128), (uint16_t)(f + 1), 0, nearness()};
          dsave(&W, &snaps[ncell]); addHash(key, ncell); ncell++;
        }
      }
    }
    macros++;
  }
  if (verifyN) {   // проверка повтора в этом же процессе: старт + цепочка -> та же точка, что в снимке ячейки
    int done = 0;
    for (int i = 0; i < ntg && done < verifyN; i++) { Target *t = &tg[i]; if (!t->reached) continue; done++;
      int chain[4096], n = 0; for (int c = t->cell; c >= 0 && n < 4096; c = cells[c].parent) chain[n++] = c;
      const Start *st = &starts[cells[chain[n - 1]].seed];
      dload(&W, &snaps[t->cell]); float cx = W.car.x, cz = W.car.z;
      bwLoad(&W, &S0); bwPlace(&W, st->x, st->y, st->z, st->h); for (int k = 0; k < 30; k++) bwStep(&W, 0, 0, 0);
      for (int k = n - 2; k >= 0; k--) { const Cell *C = &cells[chain[k]];
        for (int fr = 0; fr < C->frames; fr++) { unsigned b; float ax, ay; macroInput(C->kind, C->a, C->b + 128, fr, C->frames, &b, &ax, &ay); bwStep(&W, b, ax, ay); } }
      fprintf(stderr, "  проверка %s: снимок ячейки %.2f %.2f, повтор цепочки %.2f %.2f (цепочка %d)\n", t->name, cx, cz, W.car.x, W.car.z, n);
    }
  }
  int nr = 0; for (int i = 0; i < ntg; i++) nr += tg[i].reached;
  fprintf(stderr, "explorer: макросов %ld, кадров %ld (%.0f мин игры), ячеек %d, целей достигнуто %d из %d, проб «заперт» %d\n", macros, frames, frames / 3600.f, ncell, nr, ntg, probeN);
  if (coOn) { coDump(); fprintf(stderr, "explorer: анатомия — мест %u, переходов по земле %u, проб «машина заперта» %d -> %s\n", coN, coEN, carProbeN, coDir); }
  for (int i = 0; i < ntg; i++) {
    Target *t = &tg[i];
    printf("T\t%s\t%s\t%.1f\t%.1f\t%.1f\t%d\t%.1f\t%.1f\t%.1f\t%.1f\t%.1f\t%.1f\t%d\n", t->kind, t->name, t->x, t->y, t->z, t->reached, t->reached ? t->t : -1.f,
           t->bd > 1e8f ? -1.f : t->bd, t->bh, t->bx, t->by, t->bz, t->bfoot);   // лучший подход: плоскость, нехватка высоты, где, пешком
    if (t->reached && out) writeRepro(out, t);
  }
  for (int i = 0; i < nev; i++) { const Event *e = &ev[i]; char file[64], what[96];
    snprintf(file, sizeof file, "ev_%s_%d_%d_L%d_%s", evName[e->kind], e->gx * 8, e->gz * 8, e->layer, e->obj); snprintf(what, sizeof what, "событие %s", evName[e->kind]);
    printf("E\t%s\t%.1f\t%.1f\t%.1f\t%d\t%.1f\t%s\t%d\t%s\n", evName[e->kind], e->x, e->y, e->z, e->n, e->t, file, e->layer, e->obj);
    if (out) writeChain(out, file, what, e->t, e->cell, e->mk, e->ma, e->mb, e->mfr, e->frame); }
  printf("S\t%ld\t%ld\t%d\t%d\n", macros, frames, ncell, cap);   // ncell == cap: архив полон, новые места дальше не добавлялись
  return 0;
}
