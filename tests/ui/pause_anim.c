// №631: хост-проверка позы рамки паузы (viewer/ui_anim.h uiPausePose) по записи PS2: открытие 0,16 с 0,40 -> 1, закрытие 0,06 с 1 -> 0,80 -> 0,74. Красный контроль: argv[1]="still" — без анимации.
#include <stdio.h>
#include <string.h>
#include "ui_anim.h"
static int bad;
#define CK(c, m) do { if (!(c)) { printf("FAIL %s\n", m); bad = 1; } } while (0)
int main(int argc, char **argv) {
  int still = argc > 1 && !strcmp(argv[1], "still"); float s, a; int r;
  r = uiPausePose(0, 0.f, &s, &a); if (still) s = 1.f; CK(r && s < .5f, "открытие стартует с малой рамки");
  r = uiPausePose(0, .06f, &s, &a); CK(r && s > .6f && s < .7f, "кадр 31: ~0,63");
  r = uiPausePose(0, .159f, &s, &a); CK(r && s > .86f, "к концу почти полный размер");
  r = uiPausePose(0, .17f, &s, &a); CK(!r, "после 0,16 с анимации нет");
  r = uiPausePose(1, .021f, &s, &a); CK(r && s > .79f && s < .81f, "закрытие: 0,80");
  r = uiPausePose(1, .041f, &s, &a); CK(r && s > .73f && s < .75f, "закрытие: 0,74");
  r = uiPausePose(1, .061f, &s, &a); CK(!r, "после 0,06 с закрытие кончилось");
  puts(bad ? "FAIL" : "PASS"); return bad;
}
