// №909: переключение дали 150 <-> 250 м по настоящей трассе проезда (строки HZT смоука: кадр, высота глаза, высота над землёй под глазом, ey ячейки ленты) — Мак, только файлы.
// Печатает на каждую трассу: TRACE файл frames=N toggles=K hi_frames=M; по искусственной «прыжок с дрожью у порога»: SYNTH episodes=E
#include <stdio.h>
#include <stdlib.h>
#include "../../viewer/far909.h"
#define FAR150_UP 8.f
int main(int argc, char **argv) {
  unsigned totalToggles = 0;
  for (int a = 1; a < argc; a++) {
    FILE *f = fopen(argv[a], "r"); if (!f) { printf("FAIL: нет %s\n", argv[a]); return 2; }
    char ln[256]; unsigned fr, n = 0, tg = 0, hiN = 0; float ey, clr, cey; Far909 st = {0, 0.f}; int prev = 0;
    while (fgets(ln, sizeof ln, f)) {
      if (sscanf(ln, "%u %f %f %f", &fr, &ey, &clr, &cey) != 4) continue;
      int old = !(ey < cey + FAR150_UP), hi = far909Step(&st, clr < -990.f ? -1e9f : clr, old, 1.f / 30.f);   // как в main_loop.h
      if (n && hi != prev) tg++; prev = hi; hiN += hi; n++;
    }
    fclose(f); printf("TRACE %s frames=%u toggles=%u hi_frames=%u\n", argv[a], n, tg, hiN); totalToggles += tg;
  }
  // искусственная: земля -> прыжок до 20 м -> дрожь у порога 11…13 м при спуске -> земля; ожидаем один эпизод «высокого взгляда»
  Far909 st = {0, 0.f}; int prev = 0; unsigned ep = 0;
  for (int i = 0; i < 300; i++) {
    float clr = i < 30 ? 3.f : i < 60 ? 3.f + (i - 30) * .6f : i < 120 ? 21.f - (i - 60) * .13f + ((i & 1) ? .8f : -.8f) : i < 180 ? 13.f - (i - 120) * .1f + ((i & 1) ? .8f : -.8f) : 3.f;
    int hi = far909Step(&st, clr, 0, 1.f / 30.f); if (hi && !prev) ep++; prev = hi;
  }
  printf("SYNTH episodes=%u\n", ep);
  printf("TOTAL toggles=%u synth_episodes=%u\n", totalToggles, ep);
  return (totalToggles == 0 && ep == 1) ? 0 : 1;
}
