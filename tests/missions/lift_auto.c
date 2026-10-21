/* №519: подъёмник Duff и платформы Toggle (АЭС) едут сами, когда Гомер встал на платформу; с любого ящика Duff до верхнего уровня ≥ 6,7 м (крыша 8,4, прыжок 1,88).
   Хост: aoStep на мире уровня из бот-стенда. Использование: BW_LEVEL=N lift_auto level.shr homer.shr level0N.msn [lift|toggle]. Красные контроли: -DDUFF_LIFT_OLD=1,
   -DDUFF_LIFT_BOOST_OLD=1 (верх низкого ящика), -DTOGGLE_AUTO_OLD=1. Код возврата 0 — PASS по выбранной части. */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
static float boxTop(const ColBox *b) { return b->c[1] + fabsf(b->ax[1]) * b->h[0] + fabsf(b->ay[1]) * b->h[1] + fabsf(b->az[1]) * b->h[2]; }
int main(int argc, char **argv) {
  if (argc < 5 || bwData(argv[1], argv[2], argv[3])) return 2;
  int wantLift = !strcmp(argv[4], "lift"); static BotWorld W; if (bwNew(&W) || !W.haveAo) return 2;
  ColWorld *cw = (ColWorld *)bwCol(); int checked = 0, bad = 0;
  for (unsigned k = 0; k < W.ao.nobj; k++) {
    const AoObj *o = &W.ao.obj[k]; if (!o->nVol) continue;
    if (wantLift ? o->action != AO_PLAYANIM : o->action != AO_TOGGLE) continue;
    for (unsigned bx = o->firstVol; bx < (unsigned)o->firstVol + o->nVol; bx++) {   // каждый ящик по очереди: Гомер стоит на нём
      if (W.ao.vol[bx].kind != 0) continue;
      BotWorld *Wp = &W; (void)Wp;
      static BotSnap snap; static int haveSnap; if (!haveSnap) { bwSaveAlloc(&W, &snap); haveSnap = 1; }
      bwSave(&W, &snap);
      const ColBox *b = &cw->box[W.ao.vol[bx].col]; float x = b->c[0], z = b->c[2], y0 = boxTop(b), top = y0, tMove = -1.f, tStart = -1.f;
      aoStep(&W.ao, &W.sp, cw, x, y0 - 3.f, z, 1, 0, 1.f / 30.f);   // сначала Гомер внизу — ничего не едет
      if (W.ao.run[k].playing) { bwLoad(&W, &snap); continue; }
      for (int f = 0; f < 420; f++) {
        aoStep(&W.ao, &W.sp, cw, x, y0, z, 1, 0, 1.f / 30.f);   // ноги на старой высоте верха ящика, пока он не уехал
        if (W.ao.run[k].playing && tStart < 0.f) tStart = f / 30.f;
        float t = boxTop(&cw->box[W.ao.vol[bx].col]); if (t > top) top = t;
        float hd = hypotf(cw->box[W.ao.vol[bx].col].c[0] - x, cw->box[W.ao.vol[bx].col].c[2] - z); if (tMove < 0.f && (t - y0 > .1f || hd > .3f)) tMove = f / 30.f;
      }
      bwLoad(&W, &snap);
      int started = tStart >= 0.f && tStart < .1f;
      printf("объект %u ящик %u: верх в покое %.2f, максимум %.2f, запуск %s, движение через %.2f с\n", k, bx - o->firstVol, y0, top, started ? "сразу" : "НЕТ", tMove);
      if (!started) continue;   // неподвижный ящик (крыша, сам лифт 22,6 м) или объект не платформа — не проверяем
      checked++;
      if (wantLift && top - y0 > .8f && top - y0 < 3.f + 4.f && y0 < 7.f && o->nVol <= 6 && (top < 6.7f || tMove < 0.f || tMove > .6f)) bad = 1;   // Duff: с любого ящика верх ≥ 6,7 м и поехал быстро
      if (!wantLift && (tMove < 0.f || tMove > .6f)) bad = 1;   // платформа АЭС трогается быстро после посадки
    }
  }
  printf("%s: проверено ящиков %d\n", bad || !checked ? "FAIL" : "PASS", checked); return bad || !checked ? 1 : 0;
}
