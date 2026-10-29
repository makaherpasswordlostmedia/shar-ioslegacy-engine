// Игра без экрана (пункт Б0): командная строка поверх tools/bots/world.c.
//   game_headless LEVEL HOMER --input FILE      проиграть ввод; строки "N кнопки ax ay" (N кадров подряд, кнопки — hex/десятичные
//                                               биты GP_* = PSP_CTRL_*), '#' — комментарий; в stdout отпечаток и счётчики
//   game_headless LEVEL HOMER --selftest [--seed S] [--secs T]
//                                               гейты Б0: (1) один ввод дважды = мир побайтно; (2) сохранить -> 10 с -> загрузить
//                                               -> те же 10 с = те же байты; печатает отпечатки для сверки между процессами
//   game_headless LEVEL HOMER --gen SEED SECS   напечатать ввод-«водителя» (для --input)
//   --msn build/missions/level01.msn            миссии уровня внутри (viewer/game_msn.c), их ход — в отпечатке мира
//   --mission N                                 (с --input) сразу начать миссию N, как пункт MISSION SELECT меню паузы
//   --start X Y Z H                             (с --input) машина в точку до ввода (повторы исследователя)
//   --plant-car X Y Z H                         (с --input) гейт Т1.2: стоящая машина (место 0 из данных) — препятствием в точку
//   --stitch K                                  (с --input) как бот: каждые K кадров сохранить мир, пройти K/2 кадров, загрузить и
//                                               пройти их заново (исследователь продолжает из снимков) — итог обязан совпасть с прямым
// Сборка: tools/bots/build.sh (флаг -DBW_BREAK_LOAD=1 — отрицательный контроль: загрузка без монет обязана поймать FAIL).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

typedef struct { unsigned b; float ax, ay; } Frame;
static uint32_t rs;
static uint32_t xr(void) { rs ^= rs << 13; rs ^= rs >> 17; rs ^= rs << 5; return rs; }
// «водитель» для проверок: отрезки по 0.5–3 с — газ с рулём, ручник, тормоз, стоп и выход (△), пешком шаг или бег (○)/прыжок/пинок,
// обратно в машину (△), изредка RESET CAR (START); одно нажатие кнопки — один кадр
static Frame *genInput(uint32_t seed, int frames) {
  Frame *f = calloc((size_t)frames, sizeof *f); rs = seed ? seed : 1;
  int i = 0, onFoot = 0;
  while (i < frames) {
    int len = 30 + (int)(xr() % 150), mode = (int)(xr() % 8); float steer = ((int)(xr() % 201) - 100) / 100.f;
    for (int k = 0; k < len && i < frames; k++, i++) {
      unsigned b = 0; float ax = 0, ay = 0;
      if (!onFoot) {
        if (mode <= 3) { b |= GP_R; ax = steer * (mode == 3 ? sinf(k * .05f) : 1.f); }
        else if (mode == 4) { b |= GP_R | GP_SQUARE; ax = steer; }
        else if (mode == 5) { b |= GP_L; }
        else if (mode == 6) { if (k == len - 1) { b |= GP_TRIANGLE; onFoot = 1; } else b |= GP_L; }   // встать и выйти
        else if (k == 0 && xr() % 4 == 0) b |= GP_START;
      } else {
        ay = -1.f; ax = steer;
        if (mode < 4) b |= GP_CIRCLE;                         // половина отрезков бегом: ○ зажат (DASH / SPRINT), иначе шагом
        if (k % 40 == 10) b |= GP_CROSS; if (k % 55 == 20) b |= GP_SQUARE;
        if (mode >= 6 && k == len - 1) { b |= GP_TRIANGLE; onFoot = 0; }
      }
      f[i] = (Frame){b, ax, ay};
    }
  }
  return f;
}
static void run(BotWorld *w, const Frame *f, int a, int b) { for (int i = a; i < b; i++) bwStep(w, f[i].b, f[i].ax, f[i].ay); }

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: game_headless LEVEL HOMER --input FILE | --selftest [--seed S --secs T] | --gen SEED SECS\n"); return 2; }
  const char *msn = 0;
  for (int i = 4; i < argc; i++) if (!strcmp(argv[i], "--msn") && i + 1 < argc) msn = argv[++i];
  if (bwData(argv[1], argv[2], msn)) { fprintf(stderr, "game_headless: нет данных уровня/Гомера/миссий\n"); return 2; }
  uint32_t seed = 7; float secs = 60;
  for (int i = 4; i < argc; i++) {
    if (!strcmp(argv[i], "--seed") && i + 1 < argc) seed = (uint32_t)strtoul(argv[++i], 0, 10);
    else if (!strcmp(argv[i], "--secs") && i + 1 < argc) secs = (float)atof(argv[++i]);
  }
  static BotWorld w;
  if (!strcmp(argv[3], "--gen")) {
    if (argc < 6) return 2;
    int n = (int)(atof(argv[5]) * 60); Frame *f = genInput((uint32_t)strtoul(argv[4], 0, 10), n);
    for (int i = 0; i < n; ) { int j = i; while (j < n && f[j].b == f[i].b && f[j].ax == f[i].ax && f[j].ay == f[i].ay) j++;
      printf("%d %x %.9g %.9g\n", j - i, f[i].b, f[i].ax, f[i].ay); i = j; }
    return 0;
  }
  if (!strcmp(argv[3], "--input")) {
    if (argc < 5) return 2;
    FILE *in = fopen(argv[4], "r"); if (!in) return 2;
    bwNew(&w); char ln[1024]; int frames = 0; int trace = getenv("GH_TRACE") ? atoi(getenv("GH_TRACE")) : 0; int voidLog = getenv("GH_VOID") != 0, voidWas = 0; int watch = getenv("GH_PROP") ? atoi(getenv("GH_PROP")) : -1, watchWas = 0, watchN = 0; (void)watchN;   // строка-комментарий повтора бывает длиннее 128
    for (int i = 4; i < argc; i++) if (!strcmp(argv[i], "--mission") && i + 1 < argc && w.haveMsn) msn_start_mission(&w.msn.rt, atoi(argv[++i]), 0);   // как MISSION SELECT
    for (int i = 4; i < argc; i++) if (!strcmp(argv[i], "--start") && i + 4 < argc) {   // старт в точке (как bwPlace у ботов)
      float x = (float)atof(argv[i + 1]), y = (float)atof(argv[i + 2]), z = (float)atof(argv[i + 3]), h = (float)atof(argv[i + 4]); bwPlace(&w, x, y, z, h); i += 4; }
    for (int i = 4; i < argc; i++) if (!strcmp(argv[i], "--plant-car") && i + 4 < argc) { bwPlantCar((float)atof(argv[i + 1]), (float)atof(argv[i + 2]), (float)atof(argv[i + 3]), (float)atof(argv[i + 4])); i += 4; }
    int stitch = 0; for (int i = 4; i < argc; i++) if (!strcmp(argv[i], "--stitch") && i + 1 < argc) stitch = atoi(argv[++i]);
    BotSnap ss; int nsave = 0; if (stitch > 1) bwSaveAlloc(&w, &ss);
    Frame *seq = 0; int nseq = 0, capseq = 0;   // сшитый повтор: ввод по кадрам целиком
    while (fgets(ln, sizeof ln, in)) {
      if (ln[0] == '#') continue; int n; unsigned b; float ax, ay;
      if (sscanf(ln, "%d %x %f %f", &n, &b, &ax, &ay) != 4) continue;
      if (stitch > 1) { for (int k = 0; k < n; k++) { if (nseq == capseq) { capseq = capseq ? capseq * 2 : 4096; seq = realloc(seq, sizeof(Frame) * (size_t)capseq); }
          seq[nseq++] = (Frame){b, ax, ay}; } continue; }
      for (int k = 0; k < n; k++, frames++) {
        bwStep(&w, b, ax, ay);
        if (watch >= 0 && w.haveProps && (unsigned)watch < w.props.ninst && w.props.st[watch].hidden != watchWas) {   // GH_PROP=i: смена «спрятан»
          watchWas = w.props.st[watch].hidden; watchN++;
          fprintf(stderr, "предмет %d: %s на кадре %d (машина %.1f %.1f)\n", watch, watchWas ? "разбит/спрятан" : "снова на месте", frames, w.car.x, w.car.z); }
        if (voidLog && w.homer.voidFloors != voidWas) { voidWas = w.homer.voidFloors; fprintf(stderr, "пол над пустотой кадр %d\n", frames); }   // GH_VOID=1: гейт tests/falls/void_floor
        if (trace && frames % trace == 0) { int ft = gameOnFoot(&w.G);   // GH_TRACE=N: игрок каждые N кадров (stderr)
          fprintf(stderr, "кадр %d %s %.3f %.3f %.3f на земле %d vy %.2f ввод %x %.2f %.2f состояние %d\n", frames, ft ? "Гомер" : "машина", ft ? w.homer.x : w.car.x,
                  ft ? w.homer.y : w.car.y, ft ? w.homer.z : w.car.z, ft ? w.homer.grounded : w.car.grounded, ft ? w.homer.vy : w.car.vy, b, ax, ay, w.homer.state); }
      }
    }
    fclose(in);
    if (stitch > 1) {   // как исследователь: снимок -> K/2 кадров -> загрузка -> те же K/2 заново -> дальше
      for (int i = 0; i < nseq; ) {
        if (i % stitch == 0) { bwSave(&w, &ss); int e = i + stitch / 2 < nseq ? i + stitch / 2 : nseq; for (int j = i; j < e; j++) bwStep(&w, seq[j].b, seq[j].ax, seq[j].ay); bwLoad(&w, &ss); nsave++; }
        bwStep(&w, seq[i].b, seq[i].ax, seq[i].ay); i++; frames++;
      }
      fprintf(stderr, "сшитый повтор: %d загрузок снимка\n", nsave); bwSnapFree(&ss); free(seq);
    }
    { int tc, tp, tk; if (bwTrafficCounts(&tc, &tp, &tk)) printf("трафик: машин %d, пешеходов %d, стоящих мест %d, событий %u\n", tc, tp, tk, w.st.trEvents); else printf("трафик: нет\n"); }
    printf("кадров %d (%.1f с игры); отпечаток %016llx; машина %.2f %.2f %.2f; пешком %d; удары предметов %u, стейтпропы %u, монеты %u (кошелёк %d), "
           "события Гомера %u, RESET %u, шкала H&R %.3f, сильнейший удар о стену %.1f м/с\n", frames, frames / 60.f, (unsigned long long)bwHash(&w),
           w.car.x, w.car.y, w.car.z, gameOnFoot(&w.G), w.st.propKicks, w.st.spChanges, w.st.coins, w.haveCoins ? w.coins.collected : 0,
           w.st.homerEvents, w.st.resets, w.hnrHeat, w.st.maxWallV);
    // для сверки повторов исследователя: где игрок (Гомер, если пешком), какие монеты мира собраны, какие предметы разбиты
    int foot = gameOnFoot(&w.G);
    printf("игрок %.4f %.4f %.4f; на земле %d; скорость %.4f\nмонеты мира собраны:", foot ? w.homer.x : w.car.x, foot ? w.homer.y : w.car.y,
           foot ? w.homer.z : w.car.z, foot ? w.homer.grounded : w.car.grounded, foot ? 0.f : fabsf(w.car.v));
    for (unsigned i = 0; w.haveCoins && i < w.coins.nworld; i++) if (!w.coins.c[i].active) printf(" %u", i);
    printf("\nпредметы спрятаны:");
    for (unsigned i = 0; w.haveProps && i < w.props.ninst; i++) if (w.props.st[i].hidden) printf(" %u", i);
    printf("\n");
    return 0;
  }
  if (!strcmp(argv[3], "--selftest")) {
    int n = (int)(secs * 60), mid = n / 2, ten = 600;
    Frame *f = genInput(seed, n + ten);
    // (1) один ввод дважды: свежий мир, покадровые отпечатки совпадают
    uint64_t *h1 = malloc(sizeof(uint64_t) * (size_t)n); int diff1 = -1;
    bwNew(&w); for (int i = 0; i < n; i++) { bwStep(&w, f[i].b, f[i].ax, f[i].ay); h1[i] = bwHash(&w); }
    BotStats s1 = w.st; float x1 = w.car.x, z1 = w.car.z; bwFree(&w);
    bwNew(&w); for (int i = 0; i < n; i++) { bwStep(&w, f[i].b, f[i].ax, f[i].ay); if (diff1 < 0 && bwHash(&w) != h1[i]) diff1 = i; }
    printf("(1) ввод дважды, %d кадров: %s; отпечаток конца %016llx; машина %.1f %.1f; удары предметов %u, стейтпропы %u, монеты %u, RESET %u, событий Гомера %u\n",
           n, diff1 < 0 ? "побайтно одинаково" : "РАЗОШЛОСЬ", (unsigned long long)h1[n - 1], x1, z1, s1.propKicks, s1.spChanges, s1.coins, s1.resets, s1.homerEvents);
    if (diff1 >= 0) printf("    первое расхождение на кадре %d\n", diff1);
    bwFree(&w);
    // (2) сохранить в середине -> 10 с -> загрузить -> те же 10 с
    bwNew(&w); run(&w, f, 0, mid);
    BotSnap s; bwSaveAlloc(&w, &s); bwSave(&w, &s);
    uint64_t *h2 = malloc(sizeof(uint64_t) * ten); int diff2 = -1;
    for (int i = 0; i < ten; i++) { bwStep(&w, f[mid + i].b, f[mid + i].ax, f[mid + i].ay); h2[i] = bwHash(&w); }
    bwLoad(&w, &s);
    for (int i = 0; i < ten; i++) { bwStep(&w, f[mid + i].b, f[mid + i].ax, f[mid + i].ay); if (diff2 < 0 && bwHash(&w) != h2[i]) diff2 = i; }
    printf("(2) сохранить на %.1f с -> 10 с -> загрузить -> те же 10 с: %s\n", mid / 60.f, diff2 < 0 ? "побайтно одинаково" : "РАЗОШЛОСЬ");
    if (diff2 >= 0) printf("    первое расхождение через %d кадров после загрузки\n", diff2);
    { int tc, tp, tk; if (bwTrafficCounts(&tc, &tp, &tk)) printf("трафик в мире: машин %d, пешеходов %d, стоящих мест %d, событий %u\n", tc, tp, tk, w.st.trEvents); else printf("трафик в мире: нет\n"); }
    { int cg, au; bwMissionPacks(&cg, &au); printf("пакеты миссий рядом с уровнем: кузовов машин %d, звук миссий %s\n", cg, au ? "есть" : "нет"); }
    printf("RESULT: %s\n", diff1 < 0 && diff2 < 0 ? "OK" : "FAIL");
    bwSnapFree(&s); bwFree(&w);
    return diff1 < 0 && diff2 < 0 ? 0 : 1;
  }
  return 2;
}
