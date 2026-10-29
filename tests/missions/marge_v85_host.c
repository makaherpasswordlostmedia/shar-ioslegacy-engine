// В85 (ДОБИВКА 21, 09.10): Мардж на старте m0 L1 и повтор △ после Cancel — игра без экрана, тот же код логики, что EBOOT
// (viewer/game_msn.c). Эталон — факт ../shar-psp-ps2-w/knowledge/facts/ps2-marge-distance-cancel-window.yaml (записи PS2
// build/twins/o4/ps2_v85_*; координаты порта = PS2 с z с обратным знаком):
//   A  старт m0 как NEW GAME, 10 с без ввода: Мардж стоит 1.473..1.572 м от Гомера (PS2 ps2_v85_marge_rtti_bound); порт до
//      правки — 0.612 м. Допуск сверху — один шаг ходьбы 0.87/60 м (порт останавливает шагом, Гомер не качается)
//      Потом Гомер уходит с её пути — она стоит (ПРАВИЛО ПОРТА: маршрут окончен; на PS2 этот случай не записан)
//   B  Гомер на месте, откуда PS2 позвал Мардж (атлас m0d кадр 90: 219.833/−176.218), △ -> разговор (места SetDialoguePositions,
//      2.541 м как у PS2), Cancel -> оба там, где стояли до разговора (ПРАВИЛО ПОРТА; для Гомера = PS2 219.832/−176.218), Мардж
//      стоит 2 с (PS2: 140 кадров без движения)
//   D  абсолютные места после Cancel против PS2 (ps2_v85_cancel_triangle_base кадр 40+): Гомер 219.832/−176.218, Мардж
//      220.097/−177.042, 0.866 м; допуск 0.01 м, как сдвиг в B. Где Мардж стояла перед △ на PS2, не записано — у порта она после
//      Cancel там, где остановилась в A, и D это расхождение показывает (часть D отдельно: marge_v85.sh печатает её итог)
//   C  повтор △ после Cancel кадрами PAL (dt 0.02): +8/+16/+24 — отказ, и позже само не открывается; +26/+28/+32 — разговор
//      (PS2 ps2_v85_cancel_retalk_N). Места перед повтором ставятся одинаково в обоих режимах — проверяется только окно
//   marge_v85 LEVEL HOMER MSN [A|B|C|D]  -> строки "V85 ..." и "RESULT OK|FAIL"
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"

static BotWorld W;
static GameNpc *marge(void) { return (GameNpc *)gameMsnNpc(&W.msn, "marge"); }
static float dist(const GameNpc *n) { return hypotf(W.homer.x - n->pos.x, W.homer.z - n->pos.z); }
static int talking(void) { return W.msn.talk.on || W.msn.rt.obj == MSN_OBJ_DIALOGUE; }
static const float PS2_HX = 219.832f, PS2_HZ = 176.218f;   // Гомер перед △ и после карточки (PS2 z = −176.218)
static const float PS2_MX = 220.097f, PS2_MZ = 177.042f, PS2_D = 0.865564f;   // Мардж после Cancel, расстояние (факт after_cancel)

// новый m0, Мардж дошла и стоит (A). 0 — ок
static int startM0(float *dEnd, float *dMin, float *dMax) {
  bwNew(&W);
  GameNpc *n = marge();
  if (!W.haveMsn || !W.haveHomer || !n || !gameOnFoot(&W.G) || W.msn.rt.obj != MSN_OBJ_TALKTO) return 1;
  float lo = 1e9f, hi = 0.f;
  for (int f = 0; f < 600; f++) { bwStep(&W, 0, 0, 0); if (f >= 300) { float d = dist(n); if (d < lo) lo = d; if (d > hi) hi = d; } }
  *dEnd = dist(n); *dMin = lo; *dMax = hi;
  return 0;
}
// Гомер к месту PS2 перед △, △ -> разговор. 0 — разговор начался; pre — где стояли до △
static int talkFromPs2Spot(float pre[4]) {
  GameNpc *n = marge();
  homerPlace(&W.homer, bwCol(), PS2_HX, W.homer.y + .3f, PS2_HZ, atan2f(n->pos.x - PS2_HX, n->pos.z - PS2_HZ));
  for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
  pre[0] = W.homer.x; pre[1] = W.homer.z; pre[2] = n->pos.x; pre[3] = n->pos.z;
  bwStep(&W, GP_TRIANGLE, 0, 0);
  for (int f = 0; f < 60 && !talking(); f++) bwStep(&W, 0, 0, 0);
  return !talking();
}

int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "marge_v85: нет данных\n"); return 2; }
  const char *only = argc > 4 ? argv[4] : "ABC";   // D — только по имени (marge_v85.sh: отдельный итог, открытое расхождение)
  int bad = 0;
  if (strchr(only, 'A')) {
    float e, lo, hi;
    if (startM0(&e, &lo, &hi)) { printf("V85 A: m0 не стартовал (Мардж, Гомер пешком, цель talkto)\nRESULT FAIL\n"); return 2; }
    const float need0 = 1.473076f, need1 = 1.572168f + .87f / 60.f;
    int fail = !(e >= need0 && e <= need1 && lo >= need0 && hi <= need1);
    printf("V85 A старт m0, 10 с: Мардж %.3f/%.3f, расстояние конец %.3f м, мин %.3f, макс %.3f (PS2 1.473..1.572, +шаг %.4f) -> %s\n",
           marge()->pos.x, marge()->pos.z, e, lo, hi, .87f / 60.f, fail ? "FAIL" : "ok");
    bad += fail;
    {   // Гомер уходит с её пути к месту PS2 перед △ — она стоит (маршрут окончен), 3 с
      GameNpc *n = marge(); float mx = n->pos.x, mz = n->pos.z, moved = 0.f;
      homerPlace(&W.homer, bwCol(), PS2_HX, W.homer.y + .3f, PS2_HZ, 0.f);
      for (int f = 0; f < 180; f++) { bwStep(&W, 0, 0, 0); float q = hypotf(n->pos.x - mx, n->pos.z - mz); if (q > moved) moved = q; }
      int f2 = moved > .01f;
      printf("V85 A Гомер ушёл с пути (к %.3f/%.3f): Мардж за 3 с прошла %.3f м (правило порта: маршрут окончен) -> %s\n", PS2_HX, PS2_HZ, moved, f2 ? "FAIL" : "ok");
      bad += f2;
    }
    bwFree(&W);
  }
  if (strchr(only, 'B')) {
    float e, lo, hi, pre[4];
    if (startM0(&e, &lo, &hi) || talkFromPs2Spot(pre)) { printf("V85 B: разговор не начался\nRESULT FAIL\n"); return 2; }
    GameNpc *n = marge();
    float dTalk = dist(n);
    printf("V85 B разговор: Гомер %.3f/%.3f, Мардж %.3f/%.3f, %.3f м (PS2 места разговора 2.541)\n", W.homer.x, W.homer.z, n->pos.x, n->pos.z, dTalk);
    gameMsnTalkCancel(&W.msn);
    n = marge();
    float eh = hypotf(W.homer.x - pre[0], W.homer.z - pre[1]), em = n ? hypotf(n->pos.x - pre[2], n->pos.z - pre[3]) : 1e9f;
    float dPre = hypotf(pre[0] - pre[2], pre[1] - pre[3]), d0 = n ? dist(n) : 0.f, mx = n ? n->pos.x : 0.f, mz = n ? n->pos.z : 0.f, moved = 0.f;
    for (int f = 0; f < 120 && n; f++) { bwStep(&W, 0, 0, 0); float q = hypotf(n->pos.x - mx, n->pos.z - mz); if (q > moved) moved = q; }
    int back = W.msn.rt.obj == MSN_OBJ_TALKTO && !W.msn.talk.on;
    int fail = !n || !back || eh > .01f || em > .01f || moved > .01f || fabsf(dTalk - 2.541f) > .05f;
    printf("V85 B Cancel: Гомер %.3f/%.3f (до △ %.3f/%.3f, сдвиг %.3f), Мардж %.3f/%.3f (до △ %.3f/%.3f, сдвиг %.3f), расстояние %.3f "
           "(до △ %.3f), за 2 с Мардж прошла %.3f м, цель talkto %d -> %s\n",
           W.homer.x, W.homer.z, pre[0], pre[1], eh, mx, mz, pre[2], pre[3], em, d0, dPre, moved, back, fail ? "FAIL" : "ok");
    bad += fail;
    bwFree(&W);
  }
  if (strchr(only, 'C')) {
    static const int K[] = {8, 16, 24, 26, 28, 32}; static const int OPEN[] = {0, 0, 0, 1, 1, 1};
    for (int i = 0; i < 6; i++) {
      float e, lo, hi, pre[4];
      if (startM0(&e, &lo, &hi) || talkFromPs2Spot(pre)) { printf("V85 C: разговор не начался\nRESULT FAIL\n"); return 2; }
      gameMsnTalkCancel(&W.msn);
      GameNpc *n = marge();   // места до разговора — одинаково в обоих режимах (проверяется только окно)
      n->pos.x = pre[2]; n->pos.z = pre[3]; n->walking = 0; n->iwp = n->nwp;
      homerPlace(&W.homer, bwCol(), pre[0], W.homer.y + .3f, pre[1], atan2f(n->pos.x - pre[0], n->pos.z - pre[1]));
      GamePad p0 = {0, 0, 0.f, 0.f}, pt = {GP_TRIANGLE, GP_TRIANGLE, 0.f, 0.f};
      int wants = 0, opened = -1; float dPress = 0.f;
      for (int f = 1; f <= 60; f++) {   // f — кадр PAL после нажатия Cancel; △ — только в кадре K
        if (f == K[i]) { wants = gameMsnWantsAction(&W.msn); dPress = dist(n); }
        gameMsnTick(&W.msn, f == K[i] ? &pt : &p0, 1.f / 50.f);
        if (opened < 0 && talking()) opened = f;   // отклонённое раннее нажатие не должно сработать и позже (до 60-го кадра)
      }
      // принято — разговор открылся после нажатия (через сколько кадров — печать; у PS2 через 4, задержка перехода этапа порта —
      // отдельный вопрос, здесь не проверяется); отказ — не открылся до 60-го кадра
      int ok = OPEN[i] ? opened >= K[i] : opened < 0;
      printf("V85 C △ через %2d кадров PAL (%.2f с) после Cancel, расстояние %.3f м, в радиусе %d: %s (PS2: %s) -> %s\n",
             K[i], K[i] / 50.f, dPress, wants, opened < 0 ? "не открыт" : opened - K[i] == 0 ? "разговор в том же кадре" : "разговор", OPEN[i] ? "разговор" : "отказ", ok ? "ok" : "FAIL");
      if (opened >= 0) printf("V85 C   разговор через %d кадров PAL после △ (PS2: 4)\n", opened - K[i]);
      bad += !ok;
      bwFree(&W);
    }
  }
  if (strchr(only, 'D')) {
    float e, lo, hi, pre[4];
    if (startM0(&e, &lo, &hi) || talkFromPs2Spot(pre)) { printf("V85 D: разговор не начался\nRESULT FAIL\n"); return 2; }
    gameMsnTalkCancel(&W.msn);
    GameNpc *n = marge();
    for (int f = 0; f < 20 && n; f++) bwStep(&W, 0, 0, 0);   // PS2: места сняты с кадра 40 после Cancel (GUI в игре с 26-го)
    if (!n) { printf("V85 D: Мардж нет после Cancel\nRESULT FAIL\n"); return 1; }
    float eh = hypotf(W.homer.x - PS2_HX, W.homer.z - PS2_HZ), em = hypotf(n->pos.x - PS2_MX, n->pos.z - PS2_MZ), d = dist(n);
    int fh = eh > .01f, fm = em > .01f, fd = fabsf(d - PS2_D) > .01f;
    printf("V85 D после Cancel против PS2: Гомер %.3f/%.3f (PS2 %.3f/%.3f, %.3f м) -> %s; Мардж %.3f/%.3f (PS2 %.3f/%.3f, %.3f м) -> %s; "
           "расстояние %.3f (PS2 %.3f) -> %s\n", W.homer.x, W.homer.z, PS2_HX, PS2_HZ, eh, fh ? "FAIL" : "ok", n->pos.x, n->pos.z, PS2_MX,
           PS2_MZ, em, fm ? "FAIL" : "ok", d, PS2_D, fd ? "FAIL" : "ok");
    bad += fh + fm + fd;
    bwFree(&W);
  }
  printf("RESULT %s\n", bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
