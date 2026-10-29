/* №517: огонь фитиля мигает как живой: смена картинки раз в 50–150 мс (6–10 раз в секунду), размер и яркость ±10 %, от часов. -DFUSE_FLICKER_OLD=1 не определяет
   fireFlicker (прежнее: 12,5 кадра/с строго по кругу) — красный контроль: проверяем те же числа на прежнем законе. */
#include <stdio.h>
#include <math.h>
#include "ui_anim.h"
int main(int argc, char **argv) {
  (void)argv; int old = argc > 1, changes = 0, last = -1, bad = 0; float tChange = 0.f, minGap = 9.f, maxGap = 0.f, smin = 9.f, smax = 0.f, amin = 9.f, amax = 0.f;
  for (int i = 0; i <= 30 * 20; i++) {   // 20 с при 30 кадрах/с
    float t = i / 30.f, s = 1.f, a = 1.f; int f;
    if (old) f = (int)(t * 12.5f) % 5 < 3 ? 0 : 3; else f = fireFlicker(t, 5, &s, &a);
    int big = f >= 3;
    if (last >= 0 && big != last) { if (changes) { float g = t - tChange; if (g < minGap) minGap = g; if (g > maxGap) maxGap = g; } changes++; tChange = t; }
    last = big; if (s < smin) smin = s; if (s > smax) smax = s; if (a < amin) amin = a; if (a > amax) amax = a;
  }
  float perSec = changes / 20.f;
  printf("смен картинки %.1f в секунду, промежутки %.3f–%.3f с, размер %.2f–%.2f, яркость %.2f–%.2f\n", perSec, minGap, maxGap, smin, smax, amin, amax);
  if (perSec < 5.f || perSec > 11.f) bad = 1;                        // 6–10 в секунду с запасом на кадр 33 мс
  if (minGap < .03f || maxGap > .2f) bad = 1;                        // 50–150 мс, кадр экрана 33 мс даёт ±33 мс округления
  if (smin < .895f || smax > 1.105f || amin < .895f || amax > 1.001f) bad = 1;
  if (smax - smin < .1f || amax - amin < .05f) bad = 1;              // дрожание есть
  printf(bad ? "FAIL\n" : "PASS\n"); return bad;
}
