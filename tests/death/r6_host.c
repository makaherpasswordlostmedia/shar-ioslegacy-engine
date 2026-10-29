// ДОБИВКА 18 (правки Роба 349/339): зоны смерти и тупик L1 R6 — хост-гейт на мире ботов (tools/bots/world.c: тот же код Гомера,
// машины, коллизии и viewer/game.c gameDeath, что EBOOT; камера пешком — homerCamera, как main.c каждый кадр).
// Сборка и прогон: tests/death/r6.sh [флаги cc]  (красный: tests/death/r6.sh -DDEATH_FOOT_OLD=1, tests/death/r6.sh -DDEADEND_OLD=1)
//
// [PS2] В86 (~/Downloads/shar-psp-ps2-w/knowledge/facts/ps2-r6-foot-death.yaml; запись build/twins/o4/ps2_v86_r6_foot_death_physics/
//   trace.tsv): Гомер пешком в R6D01 — перенос (кадр 606) в точку локатора (285,429; 5,254; 551,421 диска), курс после переноса 0°
//   (лицом по +Z диска = −Z порта = курс движка π), WalkerCam остаётся, глаз сразу (608): от Гомера (0; +1,891; +4,165) диска =
//   (0; 1,891; −4,165) порта, взгляд вниз (0; −0,209; −0,978) диска — в точку 1,0 м над ступнями; стоит так до 906.
// [PS2] В87 (ps2-r6-car-deadend.yaml; build/twins/o4/ps2_v87_deadend_gas_3s, _reverse_3s): из снимка машины над кучей покрышек
//   (259,922; 10,644; 513,894 диска; 19,17 км/ч по горизонтали, 32,99 км/ч полная) и газ, и задний ход 3 с — через забор во двор,
//   замирает у (264,97; 9,07) к кадру 60 (50 Гц: ≤ 1,2 с), DEATH-перенос в точку R6D01 со скоростью 0.
// [порт] тупик (258; −511) (вопрос В87, правки 339/349): начало машины под поверхностью кучи (замер C1: 0,76 м ниже), каждый шаг
//   отменялся (why 32). car.c DEADEND (be3c61b) ставит машину на кучу, но тупик НЕ закрыт: машина сползает к забору 462 и клинится
//   в щели «куча — забор» (второй круг 09.10). Поэтому D1–D3 меряют ИСХОД, а не глубину: они красные и на новом коде — открыто.
//
// Части (третий аргумент; tests/death/r6.sh [foot|deadend|sweep|all]):
//   foot — В86, пешком (готово):
//   F1 пешком: один перенос к R6D01 (3 м), курс Гомера после переноса π ± 0,02 (В86: 0° диска)          — красный DEATH_FOOT_OLD
//   F2 камера на кадре переноса: глаз − Гомер = (0; 1,891; −4,165) ± 0,15 м, взгляд в 1,0 ± 0,1 м над ступнями — красный DEATH_FOOT_OLD
//   F3 стоит 5 с (В86: 606…906 глаз не двигается): глаз сдвинулся < 0,05 м
//   deadend — В87, машина (открыто):
//   C1 тупик (258; −511): поза из bwPlace — начало машины под поверхностью ≥ 0,6 м (предусловие: случай воспроизведён, замер 0,76)
//   D1/D2/D3 из позы C1, газ 3 с / назад 3 с / назад 3 с и газ 3 с: за окно ввода машина перенесена DEATH или ушла от тупика
//      на ≥ 5,13 м. Числа В87: окно — ввод PS2 150 кадров 50 Гц = 3 с, оба варианта переносятся на кадре 98; 5,13 м — путь машины
//      PS2 от снимка (259,922; 513,894) до замирания во дворе (264,973; 512,996). Красные на прежнем коде И на нынешнем
//   C4/C5 снимок В87 (место PS2, скорость PS2 из таблицы, опора порта под этой точкой): газ / задний ход — DEATH-перенос к R6D01
//      не позже 1,2 с, после переноса курс π ± 0,05, скорость < 0,5 м/с (регрессия: держится и на прежнем коде)
//   sweep — рецепт замера тупика: (а) из позы C1 назад 0…6 с (шаг 0,5) и газ 5 с, руль −1/0/+1; (б) заезд как рецепт PS2
//      ps2_v87_tire_deadend_gas_repeat (поза снимка 0, газ держит 20/29/40 км/ч, курс на кромку 258; −511 ± 4 м), на куче газ 10 с.
//      Счёт: перенос / выехал (≥ 5,13 м) / стоит. Код возврата — число «стоит»
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static const float RET[3] = {285.429f, 5.254f, -551.421f};   // точка локатора R6D01 (порт: z отзеркален)
static int bad;
static void need(int ok, const char *fmt, ...) {
  char s[512]; __builtin_va_list ap; __builtin_va_start(ap, fmt); vsnprintf(s, sizeof s, fmt, ap); __builtin_va_end(ap);
  printf("%s %s\n", ok ? "ok  " : "FAIL", s); if (!ok) bad++;
}
static float wrapPi(float a) { while (a > 3.14159265f) a -= 6.2831853f; while (a < -3.14159265f) a += 6.2831853f; return a; }
static float surfAbove(float x, float y, float z) {   // поверхность над началом машины (выше y + 0,05, до +3 м); -1 — нет
  float g; return colGround(bwCol(), x, z, y + 3.f, y + .05f, &g, 0) ? g - y : -1.f;
}

static void foot(void) {
  static BotWorld w; bwNew(&w);
  bwPlace(&w, 252.f, 7.f, -522.f, 1.5708f);
  for (int i = 0; i < 30; i++) bwStep(&w, 0, 0, 0);
  for (int i = 0; i < 2; i++) bwStep(&w, GP_TRIANGLE, 0, 0);
  for (int i = 0; i < 120 && !gameOnFoot(&w.G); i++) bwStep(&w, 0, 0, 0);
  need(gameOnFoot(&w.G), "F0 Гомер вышел из машины у двора покрышек");
  // во двор (ящик 1 R6D01, x 262…287) курсом 73° диска (до переноса у PS2 73,012°; в порту курс — любой, кроме курса локатора)
  float h0 = 1.2743f;
  homerPlace(&w.homer, bwCol(), 266.f, 8.f, -515.f, h0);
  float eye[3], look[3], e0[3] = {0}, l0[3] = {0}, hAfter = 0.f; int jumps = 0, at = -1;
  for (int f = 0; f < 360; f++) {
    float px = w.homer.x, pz = w.homer.z;
    bwStep(&w, 0, 0, 0);
    homerCamera(&w.homer, bwCol(), BW_DT, eye, look);
    if (hypotf(w.homer.x - px, w.homer.z - pz) > 10.f) {
      jumps++; at = f; hAfter = w.homer.h; memcpy(e0, eye, sizeof e0); memcpy(l0, look, sizeof l0);
      printf("     перенос кадр %d -> %.2f %.2f %.2f курс %.4f; глаз %.2f %.2f %.2f, взгляд %.2f %.2f %.2f\n", f, w.homer.x, w.homer.y, w.homer.z,
             w.homer.h, eye[0], eye[1], eye[2], look[0], look[1], look[2]);
    }
  }
  float dRet = hypotf(w.homer.x - RET[0], w.homer.z - RET[2]);
  need(jumps == 1 && at >= 0 && dRet < 3.f, "F1 пешком в R6D01: переносов %d к точке локатора (%.2f м)", jumps, dRet);
  need(fabsf(wrapPi(hAfter - 3.14159265f)) < .02f, "F1 курс Гомера после переноса %.4f (В86: 0° диска = π порта; до переноса %.4f)", hAfter, h0);
  if (at < 0) { need(0, "F2/F3 нет переноса"); return; }
  float hy = w.homer.y, dx = e0[0] - w.homer.x, dy = e0[1] - hy, dz = e0[2] - w.homer.z;
  need(fabsf(dx) < .15f && fabsf(dy - 1.891f) < .15f && fabsf(dz + 4.165f) < .15f,
       "F2 глаз − Гомер на кадре переноса (%.3f; %.3f; %.3f), В86 кадр 608: (0; 1,891; −4,165) ± 0,15", dx, dy, dz);
  need(fabsf(l0[1] - hy - 1.f) < .1f && hypotf(l0[0] - w.homer.x, l0[2] - w.homer.z) < .15f,
       "F2 взгляд — в Гомера на %.3f м над ступнями (В86: 1,0)", l0[1] - hy);
  float mv = sqrtf((eye[0] - e0[0]) * (eye[0] - e0[0]) + (eye[1] - e0[1]) * (eye[1] - e0[1]) + (eye[2] - e0[2]) * (eye[2] - e0[2]));
  need(mv < .05f, "F3 стоит %d кадров после переноса: глаз сдвинулся на %.3f м (В86 606…906: стоит)", 359 - at, mv);
}

typedef struct { float retD, hAfter, vAfter; int death, deathAt; } CarRun;
// снимок В87: машина в точке со скоростью, кнопка frames кадров; первый перенос DEATH — кадр, курс и скорость после него
static CarRun carRun(float x, float y, float z, float h, const float *vel, unsigned btn, int frames) {
  static BotWorld w; bwNew(&w); bwPlace(&w, x, y, z, h);
  memcpy(w.car.vel, vel, 3 * sizeof(float));
  CarRun r = {0}; r.deathAt = -1;
  for (int f = 0; f < frames; f++) {
    float px = w.car.x, pz = w.car.z;
    bwStep(&w, btn, 0, 0);
    if (hypotf(w.car.x - px, w.car.z - pz) > 10.f && r.deathAt < 0) { r.death = 1; r.deathAt = f; r.hAfter = w.car.h; r.retD = hypotf(w.car.x - RET[0], w.car.z - RET[2]); }
    if (r.deathAt >= 0 && f == r.deathAt + 1) r.vAfter = fabsf(w.car.v);
  }
  return r;
}

#define DE_X 258.f
#define DE_Z (-511.f)
static float deAway(void) { return hypotf(264.973f - 259.922f, 512.996f - 513.894f); }   // В87: путь PS2 от снимка до замирания, 5,13 м
#define DE_WIN 180   // В87: окно ввода PS2 150 кадров 50 Гц = 3 с = 180 кадров порта
typedef struct { int death; float d, x, y, z; } DeRun;
// из позы тупика: 30 кадров покоя, затем сегменты ввода (кнопка, руль, кадров); перенос DEATH на любом сегменте — исход
static DeRun deRun(int n, const unsigned *btn, const float *ax, const int *len) {
  static BotWorld w; bwNew(&w); bwPlace(&w, DE_X, 12.f, DE_Z, 1.18f);
  DeRun r = {0, 0, 0, 0, 0};
  // The expanded air volume can return the car during the neutral settling
  // interval. Count that real transfer too, instead of labelling it "drove out".
  for (int i = 0; i < 30; i++) {
    float px=w.car.x,pz=w.car.z;bwStep(&w,0,0,0);
    if(hypotf(w.car.x-px,w.car.z-pz)>10.f && hypotf(w.car.x-RET[0],w.car.z-RET[2])<3.f)r.death=1;
  }
  for (int s = 0; s < n && !r.death; s++)
    for (int i = 0; i < len[s]; i++) {
      float px = w.car.x, pz = w.car.z; bwStep(&w, btn[s], ax[s], 0);
      if (hypotf(w.car.x - px, w.car.z - pz) > 10.f) { r.death = 1; break; }
    }
  r.d = hypotf(w.car.x - DE_X, w.car.z - DE_Z); r.x = w.car.x; r.y = w.car.y; r.z = w.car.z;
  return r;
}
static void deNeed(const char *id, const char *what, DeRun r) {
  need(r.death > 0 || r.d >= deAway(), "%s тупик, %s: перенос %s, от тупика %.2f м (нужно перенос или ≥ %.2f), конец %.2f %.2f %.2f",
       id, what, r.death > 0 ? "да" : "нет", r.d, deAway(), r.x, r.y, r.z);
}

static void deadend(void) {
  static BotWorld w; bwNew(&w); bwPlace(&w, DE_X, 12.f, DE_Z, 1.18f);
  float u = surfAbove(w.car.x, w.car.y, w.car.z);
  need(u >= .6f, "C1 тупик (258; −511): начало машины %.2f, поверхность кучи над ним на %.2f м (вопрос В87: «на 1 м ниже земли»)", w.car.y, u);
  { unsigned b[1] = {GP_R}; float a[1] = {0}; int l[1] = {DE_WIN}; deNeed("D1", "газ 3 с", deRun(1, b, a, l)); }
  { unsigned b[1] = {GP_L}; float a[1] = {0}; int l[1] = {DE_WIN}; deNeed("D2", "назад 3 с", deRun(1, b, a, l)); }
  { unsigned b[2] = {GP_L, GP_R}; float a[2] = {0, 0}; int l[2] = {DE_WIN, DE_WIN}; deNeed("D3", "назад 3 с, затем газ 3 с", deRun(2, b, a, l)); }
  // снимок В87: место PS2 (x, z), скорость PS2 — по горизонтали 19,17 км/ч курсом кадров 0→40 таблицы (4,185; 0,86 порта), вверх
  // sqrt(32,99² − 19,17²) = 26,85 км/ч; опора — порта под этой точкой (bwPlace)
  float hs = 19.17268158f / 3.6f, vv = sqrtf(32.988f * 32.988f - 19.17268158f * 19.17268158f) / 3.6f;
  float hh = atan2f(264.107f - 259.922f, -(513.034f - 513.894f)), vel[3] = {sinf(hh) * hs, vv, cosf(hh) * hs};
  for (int k = 0; k < 2; k++) {
    CarRun r = carRun(259.922f, 11.f, -513.894f, hh, vel, k ? GP_L : GP_R, 180);
    need(r.death && r.deathAt <= 72 && r.retD < 3.f && fabsf(wrapPi(r.hAfter - 3.14159265f)) < .05f && r.vAfter < .5f,
         "C%d снимок В87, %s 3 с: DEATH-перенос %d на кадре %d (≤ 72 = 1,2 с; PS2 замер к 60 из 50 Гц), к точке %.2f м, курс %.3f, скорость %.2f",
         4 + k, k ? "назад" : "газ", r.death, r.deathAt, r.retD, r.hAfter, r.vAfter);
  }
  // Exercise the actual Game query above the authored height and on the road
  // outside the fence. The OLD volume must reject the high-air sample.
  const ColWorld *cw=bwCol();const ColPad *yard=0;
  for(unsigned i=0;i<cw->ndeath;i++)if(!strcmp(cw->death[i].name,"R6D01"))yard=cw->death+i;
  if(yard){
    bwNew(&w);w.car.x=yard->c[0];w.car.z=yard->c[2];w.car.y=colZoneTop((const ColZone*)yard)+w.car.p.halfL+w.car.p.bodyHi;
    need(gameDeathAt(&w.G)>=0,"A1 воздух выше исходного R6D01 включён в DEATH");
    w.car.x=DE_X;w.car.z=DE_Z;w.car.y=yard->c[1]-w.car.p.bodyHi-w.car.modelRaise;
    need(gameDeathAt(&w.G)<0,"A2 дорога снаружи забора ниже его верха не DEATH");
    w.car.x=RET[0];w.car.z=RET[2]-w.car.p.halfL;w.car.y=colZoneTop((const ColZone*)yard)+w.car.p.halfL;
    need(gameDeathAt(&w.G)<0,"A3 вне двора за точкой возврата не DEATH");
  }else need(0,"A1 нет исходного R6D01");
}

static int sweep(void) {
  int nd = 0, no = 0, ns = 0;
  static const float sts[3] = {-1.f, 0.f, 1.f};
  for (int k = 0; k < 3; k++) for (int t = 0; t <= 12; t++) {
    unsigned b[2] = {GP_L, GP_R}; float a[2] = {sts[k], sts[k]}; int l[2] = {t * 30, 300};
    DeRun r = deRun(2, b, a, l);
    if (r.death > 0) nd++; else if (r.d >= deAway()) no++;
    else { ns++; printf("     стоит: руль %+.0f, назад %.1f с, газ 5 с -> %.2f %.2f %.2f (от тупика %.2f)\n", sts[k], t * .5f, r.x, r.y, r.z, r.d); }
  }
  printf("sweep (а) поза тупика, назад 0…6 с + газ 5 с: перенос %d, выехал %d, стоит %d\n", nd, no, ns);
  int md = 0, mo = 0, ms = 0; static const float kmhs[3] = {20.f, 29.f, 40.f};
  for (int k = 0; k < 3; k++) for (int i = 0; i <= 16; i++) {
    float aim = -4.f + .5f * i; static BotWorld w; bwNew(&w); bwPlace(&w, 242.977f, 7.f, -520.152f, 1.0236f);
    int heapF = -1, death = 0; float hx = 0, hz = 0;
    for (int f = 0; f < 1500; f++) {
      float px = w.car.x, pz = w.car.z; unsigned bt; float st = 0.f;
      if (heapF < 0 && w.car.x >= 255.5f) { heapF = f; hx = w.car.x; hz = w.car.z; }
      if (heapF < 0) { float th = atan2f(DE_X - w.car.x, DE_Z + aim - w.car.z); st = fmaxf(-1.f, fminf(1.f, -2.f * wrapPi(th - w.car.h)));
                       bt = fabsf(w.car.v) * 3.6f < kmhs[k] ? GP_R : 0; }
      else bt = GP_R;
      bwStep(&w, bt, st, 0);
      if (hypotf(w.car.x - px, w.car.z - pz) > 10.f) { death = 1; break; }
      if (heapF >= 0 && f - heapF >= 600) break;
    }
    float d = hypotf(w.car.x - hx, w.car.z - hz);
    // An air-volume return may precede the old heap-entry marker. It is a
    // completed DEATH case, not an absent/unmeasured run.
    if (heapF < 0) { if (death) md++; else ms++; continue; }
    if (death) md++; else if (d >= deAway()) mo++;
    else { ms++; printf("     стоит: заезд %.0f км/ч, кромка z %+.1f, на кучу у %.2f %.2f -> %.2f %.2f %.2f\n", kmhs[k], aim, hx, hz, w.car.x, w.car.y, w.car.z); }
  }
  printf("sweep (б) заезд (рецепт PS2 tire_deadend_gas_repeat), на куче газ 10 с: перенос %d, выехал %d, стоит %d\n", md, mo, ms);
  return ns + ms;
}

int main(int argc, char **argv) {
  if (argc < 3 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "usage: r6_host LEVEL HOMER [foot|deadend|sweep|all] (build/level.shr, build/homer.shr; traffic.shr рядом)\n"); return 2; }
  const char *part = argc > 3 ? argv[3] : "all";
  if (!strcmp(part, "sweep")) { int n = sweep(); printf("r6 sweep: %s (стоит %d)\n", n ? "FAIL" : "PASS", n); return n ? 1 : 0; }
  if (strcmp(part, "deadend")) foot();
  if (strcmp(part, "foot")) deadend();
  printf("r6 death gate [%s]: %s\n", part, bad ? "FAIL" : "PASS");
  return bad ? 1 : 0;
}
