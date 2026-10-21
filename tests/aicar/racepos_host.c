// Место игрока в гонке (правка Роба 326, 04.10: «гонка со Скиннером всё равно не считает, кто первый: ехал рядом — не понимает
// в реальном времени»; указание Роба: «кто ближе к точке — тот и первый»; прежде правки 300, 178). Те же функции, что считает игра
// каждый кадр (viewer/game_msn.c raceTrack -> viewer/msncar.c mcRacePlaceRob): точки гонки ИГРОКА для всех; больше пройдено точек —
// впереди, поровну — кто ближе по прямой к той же следующей точке; гистерезис 1 м (±0,5). Каждый вызов = кадр (состояние гистерезиса
// и счёт точек соперника живут в машине, как в игре).
// Красный (-DRACEPOS_300=1 -> mcRacePos300): нынешняя на HEAD мера правки 300 — остаток метров, у соперника по ЕГО точкам этапа
// (mcPathRemaining + mcRacePlace); обязан упасть (рядом со Скиннером на его крюке пишет «1-й»).
// Точки — с диска (art/missions/level01/*.p3d, tools/missions/p3dlocs.py, координаты движка):
//   m1 S-M-R-T: у игрока одна точка — финиш m1_AI_path4 (10.5, 623.8) (m1i.mfk:40, промежуточная закомментирована); у Скиннера
//   m1_AI_path1 (38.1, 211.3), m1_AI_path1b (154.7, 271.0), m1_AI_path4 (m1i.mfk:35–37); дорога Скиннера на север — x ≈ 230.6
//   (замер эмулятора build/twins/scen/full/racepos_new: z 295 -> 375). sr2 (3 круга): у игрока wp1–6, 8 (sr2i.mfk:54–68), у
//   соперников wp1–4, 4b, 5–7 (sr2i.mfk:43–50). m7: у игрока race1, 2, 3, 5, 6, 7, 9 (m7i.mfk:56–63), у Смитерса race1,
//   m5_smithers_nav1, race1b, race9.
// Случаи: side (рядом на одной дороге, проезд вперёд-назад: смена ровно у равного расстояния, ровно по разу), hook0/hook1 (рядом со
// Скиннером на его крюке к m1_AI_path1 / m1_AI_path1b: впереди тот, кто ближе к школе), pass (обгон в движении, 60 кадров/с),
// jitter (рядом с дрожанием ±0,3 м: место не мигает), cut (срезка дворами: ближе к школе — 1-й, дальше — 2-й), fin (Скиннер доехал),
// sr2 (круги: больше точек — впереди; счёт точек соперника, пропуск wp8 со следующей), m7 (Смитерс обходит точки игрока)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "msncar.h"
static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-8s %s  %s\n", n, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fx;
static ColWorld W;
static MsnCars M;
static const float F1[1][3] = {{10.5f, .5f, 623.8f}};   // m1: точка гонки игрока — финиш m1_AI_path4
static const float SK[3][3] = {{38.1f, 3.3f, 211.3f}, {154.7f, 3.3f, 271.0f}, {10.5f, .5f, 623.8f}};
static float dxz(const float *a, const float *b) { return hypotf(a[0] - b[0], a[2] - b[2]); }
// как игра в этом кадре: место игрока (точки гонки игрока pts/n, круги L, пройдено pk, игрок p)
static int place(const float (*pts)[3], int n, int L, int pk, const float p[3]) {
  int r = 0;
  if (mcRacePos300) return mcRacePlace(&M, mcPathRemaining(pts, n, L, pk, p), &r);
  return mcRacePlaceRob(&M, pts, n, L, pk, p, NULL, NULL, NULL, &r);
}
static McCar *rival(const char *name, const char *con, const float (*wp)[3], int nwp, int laps, float x, float z, int k) {
  mcInit(&M);
  float s[3] = {x, 0.f, z};
  McCar *c = mcSpawn(&M, &W, 0, name, s, 0.f, 1, "race", con, "x");
  for (int i = 0; i < nwp; i++) mcWaypoint(&M, i, wp[i], laps);
  if (c) { carPlace(&c->car, &W, x, .5f, z, 0.f); c->wp = k; }
  return c;
}
static void at(McCar *c, float x, float z) { c->car.x = x; c->car.z = z; }
static const char *CON1 = "Missions\\level01\\M1race.con";
// рядом: Скиннер стоит в S, игрок сбоку (lat м) проезжает вдоль направления к финишу от -10 до +10 м и обратно (шаг 0,25 м).
// Нужно: ровно одна смена вперёд и одна назад, каждая — не дальше 0,5 м + шаг от равного расстояния до финиша
static void sideCase(const char *name, float sx, float sz, int k, float lat) {
  McCar *c = rival("skinn_v", CON1, SK, 3, 1, sx, sz, k);
  const float S[3] = {sx, 0.f, sz}; float ux = F1[0][0] - sx, uz = F1[0][2] - sz, L = hypotf(ux, uz); ux /= L; uz /= L;
  int prev = 0, sw = 0, bad = 0; float worst = 0.f; char d[200];
  for (int pass = 0; pass < 2; pass++)
    for (int i = 0; i <= 80; i++) {
      float t = pass ? 10.f - .25f * i : -10.f + .25f * i;
      float p[3] = {sx + ux * t - uz * lat, 0.f, sz + uz * t + ux * lat};
      int pos = place(F1, 1, 1, 0, p);
      float gap = dxz(p, F1[0]) - dxz(S, F1[0]);   // > 0 — игрок дальше от школы
      if (prev && pos != prev) { sw++; if (fabsf(gap) > worst) worst = fabsf(gap); }
      if ((gap > 1.f && pos != 2) || (gap < -1.f && pos != 1)) bad++;
      prev = pos;
    }
  (void)c;
  snprintf(d, sizeof d, "смен места %d (нужно 2), дальше 1 м от равенства неверно: %d кадров, смена при разнице %.2f м (≤ 0,75)", sw, bad, worst);
  check(name, sw == 2 && !bad && worst <= .75f, d);
}
int main(void) {
#ifdef RACEPOS_300
  mcRacePos300 = 1;
#endif
  memcpy(fx.h.magic, "COL1", 4); fx.h.ox = fx.h.oz = -1000; fx.h.cell = 2000; fx.h.W = fx.h.H = 1; fx.h.ntri = 2; fx.h.nref = 2;
  fx.t[0] = (ColTri){{-1000, 0, -1000}, {1000, 0, 1000}, {1000, 0, -1000}, {0, 1, 0}};
  fx.t[1] = (ColTri){{-1000, 0, -1000}, {-1000, 0, 1000}, {1000, 0, 1000}, {0, 1, 0}};
  fx.start[1] = 2; fx.refs[0] = 0; fx.refs[1] = 1;
  if (colInit(&W, &fx, sizeof fx)) { printf("FAIL: мир\n"); return 1; }
  char d[200];
  // ---- m1 S-M-R-T
  sideCase("side", 230.6f, 340.f, 2, 3.5f);     // последний отрезок (на север к школе), игрок в соседней полосе
  sideCase("hook0", 75.f, 172.f, 0, 3.5f);      // Скиннер едет на запад к m1_AI_path1, игрок рядом
  sideCase("hook1", 100.f, 245.f, 1, 3.5f);     // Скиннер едет на восток к m1_AI_path1b, игрок рядом
  { // обгон в движении: оба едут к школе по прямой, Скиннер 20 м/с, игрок 22 м/с, старт игрока на 10 м сзади; кадр 1/60 с
    McCar *c = rival("skinn_v", CON1, SK, 3, 1, 230.6f, 300.f, 2);
    float ux = F1[0][0] - 230.6f, uz = F1[0][2] - 300.f, L = hypotf(ux, uz); ux /= L; uz /= L;
    int prev = 0, sw = 0, first = 0; float worst = 0.f;
    for (int f = 0; f < 600; f++) {
      float ts = 20.f * f / 60.f, tp = -10.f + 22.f * f / 60.f;
      at(c, 230.6f + ux * ts, 300.f + uz * ts);
      float p[3] = {230.6f + ux * tp - uz * 3.5f, 0.f, 300.f + uz * tp + ux * 3.5f}, S[3] = {c->car.x, 0.f, c->car.z};
      int pos = place(F1, 1, 1, 0, p); float gap = dxz(p, F1[0]) - dxz(S, F1[0]);
      if (!f) first = pos;
      if (prev && pos != prev) { sw++; worst = fabsf(gap); }
      prev = pos;
    }
    snprintf(d, sizeof d, "сначала %d (нужно 2), смен %d (нужно 1), смена при разнице %.2f м (≤ 0,6), в конце %d (нужно 1)", first, sw, worst, prev);
    check("pass", first == 2 && sw == 1 && worst <= .6f && prev == 1, d);
  }
  { // дрожание: рядом почти вровень (игрок на 0,2 м дальше), шум ±0,3 м по ходу — место не мигает
    McCar *c = rival("skinn_v", CON1, SK, 3, 1, 230.6f, 340.f, 2); (void)c;
    const float S[3] = {230.6f, 0.f, 340.f}; float ux = F1[0][0] - S[0], uz = F1[0][2] - S[2], L = hypotf(ux, uz); ux /= L; uz /= L;
    int prev = 0, sw = 0; unsigned seed = 12345;
    for (int f = 0; f < 300; f++) {
      seed = seed * 1103515245u + 12345u; float n = ((seed >> 8) & 0xFFFF) / 65535.f * .6f - .3f;
      float t = -.2f + n, p[3] = {S[0] + ux * t - uz * 3.5f, 0.f, S[2] + uz * t + ux * 3.5f};
      int pos = place(F1, 1, 1, 0, p); if (prev && pos != prev) sw++; prev = pos;
    }
    snprintf(d, sizeof d, "смен места за 300 кадров %d (нужно 0)", sw); check("jitter", sw == 0, d);
  }
  { // срезка дворами: игрок вдали от дороги Скиннера, но ближе к школе — 1-й; дальше — 2-й
    McCar *c = rival("skinn_v", CON1, SK, 3, 1, 230.8f, 335.7f, 2);
    const float p1[3] = {100.f, 0.f, 450.f}, p2[3] = {160.f, 0.f, 137.f}, S[3] = {c->car.x, 0.f, c->car.z};
    int a = place(F1, 1, 1, 0, p1), b = place(F1, 1, 1, 0, p2);
    snprintf(d, sizeof d, "двор у школы: %d (нужно 1; %0.f м против %.0f), у старта: %d (нужно 2; %.0f м против %.0f)",
             a, dxz(p1, F1[0]), dxz(S, F1[0]), b, dxz(p2, F1[0]), dxz(S, F1[0]));
    check("cut", a == 1 && b == 2, d);
  }
  { // Скиннер доехал до конца своего пути — впереди, где бы ни был игрок
    McCar *c = rival("skinn_v", CON1, SK, 3, 1, 51.4f, 635.5f, 2); c->finished = 1;
    const float p[3] = {12.f, 0.f, 620.f}; int a = place(F1, 1, 1, 0, p);
    snprintf(d, sizeof d, "место %d (нужно 2)", a); check("fin", a == 2, d);
    // у самого финиша, но ещё не доехал (финиш соперника засчитывает только миссия): кто ближе к точке
    c->finished = 0; c->rk = 0; c->rAhead = -1; at(c, 15.f, 628.f);
    const float p2[3] = {11.5f, 0.f, 625.f}; int b = place(F1, 1, 1, 0, p2);
    snprintf(d, sizeof d, "Скиннер в 6 м от точки (не доехал), игрок в 1,6 м: место %d (нужно 1), счёт точек Скиннера %d (нужно 0)", b, c->rk);
    check("fin0", b == 1 && (mcRacePos300 || c->rk == 0), d);
  }
  // ---- sr2 Circuit Race, 3 круга
  static const float rw[8][3] = {{-109, -1, 210}, {-178, 1, 160}, {-295, 6, 95}, {-314, 1, 175}, {-287, 1, 173}, {-245, 6, 102}, {-188, 1, 150}, {-204, -3, 249}};
  static const float pw[7][3] = {{-109, -1, 210}, {-178, 1, 160}, {-295, 6, 95}, {-314, 1, 175}, {-245, 6, 102}, {-188, 1, 150}, {-173, -1, 248}};
  { McCar *c = rival("honor_v", "Missions\\level01\\sr2_1st.con", rw, 8, 3, -162.f, 262.f, 0);
    // соперник едет по своим точкам: wp1..4, 4b, 5, 6, 7 (мимо wp8 игрока в 30 м) и снова wp1 — счёт точек игрока: 6, потом 8
    const float p[3] = {-162.f, 0.f, 262.f}; int rk6 = -1;
    for (int i = 0; i < 8; i++) { at(c, rw[i][0], rw[i][2]); place(pw, 7, 3, 0, p); if (i == 7) rk6 = c->rk; }
    at(c, rw[0][0], rw[0][2]); place(pw, 7, 3, 0, p);
    snprintf(d, sizeof d, "счёт точек соперника после круга без wp8: %d (нужно 6), после wp1 второго круга: %d (нужно 8)", rk6, c->rk);
    check("sr2count", mcRacePos300 || (rk6 == 6 && c->rk == 8), d);
    // соперник прошёл больше точек — впереди, хотя игрок ближе к своей точке; меньше — позади, хотя ближе он
    c->rk = 9; at(c, -240.f, 125.f); const float q[3] = {-178.f, 0.f, 162.f};
    int a = mcRacePos300 ? 0 : place(pw, 7, 3, 8, q);
    c->rk = 7; int b = mcRacePos300 ? 0 : place(pw, 7, 3, 8, q);
    snprintf(d, sizeof d, "соперник на 1 точку больше: %d (нужно 2), на 1 меньше: %d (нужно 1)", a, b);
    check("sr2laps", mcRacePos300 || (a == 2 && b == 1), d);
  }
  // ---- m7 The Fat and Furious: Смитерс едет мимо точек игрока (race2..race7) серединой города
  static const float mw[4][3] = {{223, 8, -502}, {38, 3, 211}, {-180, -2, 261}, {-183, 4, 110}};
  static const float mp[7][3] = {{223, 8, -502}, {380, -2, -343}, {342, 5, 94}, {164, 3, 269}, {124, 2, 559}, {-116, 3, 486}, {-183, 4, 110}};
  if (!mcRacePos300) {
    McCar *c = rival("smith_v", "Missions\\level01\\M7race.con", mw, 4, 1, 8.f, -292.f, 0);
    const float p0[3] = {8.f, 0.f, -292.f};
    at(c, 223.f, -500.f); place(mp, 7, 1, 0, p0);            // Смитерс в race1 (общая первая точка): прошёл 1
    at(c, 38.f, 211.f); place(mp, 7, 1, 0, p0);              // m5_smithers_nav1 — не точка игрока
    int rk = c->rk;
    const float p1[3] = {300.f, 0.f, -400.f};                 // игрок тоже прошёл race1 и ближе Смитерса к race2
    int a = place(mp, 7, 1, 1, p1);
    const float p2[3] = {164.f, 0.f, 269.f}; int b = place(mp, 7, 1, 3, p2);   // игрок прошёл 3 точки
    c->finished = 1; int e = place(mp, 7, 1, 3, p2);
    snprintf(d, sizeof d, "точек у Смитерса %d (нужно 1); игрок ближе к race2: %d (1), игрок на 3 точках: %d (1), Смитерс доехал: %d (2)", rk, a, b, e);
    check("m7", rk == 1 && a == 1 && b == 1 && e == 2, d);
  }
  printf("RESULT %s провалов %d (%s)\n", fails ? "FAIL" : "PASS", fails, mcRacePos300 ? "мера правки 300 — остаток метров по своим точкам" : "правило Роба 326");
  return fails ? 1 : 0;
}
