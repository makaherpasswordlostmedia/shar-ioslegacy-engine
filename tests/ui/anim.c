// Хост-проверка анимаций HUD (tests/ui/anim.py): та же математика, что рисует PSP (viewer/ui_anim.h), по кадрам 60 Гц.
// Режимы: argv[1] = "new" (порт сейчас) | "old" (прежний код кольца: шкала скачком, цвет по часам системы, мигалка 2/1)
//         | "pre241" (кольцо до правки 241: жёлтое до полного, красно-синее только полное, мигалка 0.628 с, выше 78 — синяя
//           половина горит, цвета мигалки) | "nopulse" (△ без пульса) | "nopop" (уведомления без всплывания) — отрицательные контроли.
// Строки: PULSE t s | HNR t target shown light col alarm | POPIN t s a | POPOUT t s a draw
// Кольцо — как viewer/ui.c uiSetHitAndRun + drawHnrFill (правка 241): цвет от настоящей шкалы, полиции (alarm) и часов elapsed
#include <stdio.h>
#include <string.h>
#include "ui_anim.h"
int main(int argc, char **argv) {
  const char *m = argc > 1 ? argv[1] : "new";
  int old = !strcmp(m, "old"), pre = !strcmp(m, "pre241"), nopulse = !strcmp(m, "nopulse"), nopop = !strcmp(m, "nopop");
  const float dt = 1.f / 60.f;
  for (int f = 0; f <= 240; f++) { float t = f * dt; printf("PULSE %.4f %.5f\n", t, nopulse ? 1.f : uiPulseScale(t)); }
  float shown = 0.f;
  for (int f = 0; f <= 9 * 60; f++) {
    float t = f * dt; int pursuit; float heat = uiHnrScriptHeat(t, &pursuit);
    int light; unsigned col;
    if (old) {   // viewer/ui.c до 28.09: fieldv = heat, мигалка sin(t*10) 2/1, цвет: синий, с 50% красный по биту 18 часов (мкс)
      shown = heat; light = pursuit ? (sinf(t * 10.f) > 0.f ? 2 : 1) : (heat > .78f ? 1 : 2);
      int v = (int)(shown * 1000.f + .5f); unsigned us = (unsigned)(t * 1e6f) + 123457u;
      col = v > 500 ? (((us >> 18) & 1) ? 0xFF2A2AE0u : 0xFF151570u) : 0xFFE08A2Au;
    } else if (pre) {   // viewer/ui_anim.h до правки 241 (коммит ea4d5c4): uiSirenFrame / uiHnrColor того времени
      shown = uiMeterFollow(shown, heat, f ? dt : 0.f);
      int v = (int)(shown * 1000.f + .5f);
      light = pursuit && v >= 1000 ? (fmodf(t, 0.6283185f) < 0.6283185f * .5f ? 0 : 1) : (heat > .78f ? 1 : 2);
      col = v < 1000 || !pursuit || light == 2 ? 0xff14e6feu : light == 0 ? 0xff1f25dcu : 0xffb35038u;
    } else {
      shown = uiMeterFollow(shown, heat, f ? dt : 0.f);
      light = uiSirenFrame(pursuit, t);
      col = uiHnrColor(pursuit, heat, t);
    }
    printf("HNR %.4f %d %d %d %08x %d\n", t, (int)(heat * 1000.f + .5f), (int)(shown * 1000.f + .5f), light, col, pursuit);
  }
  for (int k = 0; k < 2; k++)
    for (int f = 0; f <= 45; f++) {
      float t = f * dt, s = 1.f, a = 1.f; int d = 1;
      if (!nopop) d = uiPopState(k, 1, t, &s, &a);
      printf("POPIN %d %.4f %.5f %.5f %d\n", k, t, s, a, d);
      s = 1.f; a = 1.f; d = f == 0;
      if (!nopop) d = uiPopState(k, 0, t, &s, &a);
      printf("POPOUT %d %.4f %.5f %.5f %d\n", k, t, s, a, d);
    }
  return 0;
}
