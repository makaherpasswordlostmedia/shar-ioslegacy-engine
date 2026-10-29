// Гейт «1/2» в месте гонки (аудит 09.10 п. 25; knowledge/facts/ps2-race-position.yaml, запись PS2 yt-bziOipI4gDI.mp4 4:58 «1st/2»).
// Текст поля Position — viewer/ui_anim.h uiPosText (его же зовёт viewer/ui.c fmtField); число участников — viewer/msn_view.c:
// соперники гонки (gameMsnRacePos) + игрок. S-M-R-T: соперник один (Скиннер) -> «/2». Проверки:
//   pos   — место 1 и 2 при одном сопернике: «1 /2», «2 /2» (как у PS2: «1st/2», «2nd/2»; пробел — место под «st», см. ui_anim.h)
//   glyph — в спрайтовом шрифте поля Position (Hud.pag) есть «/» (проверяет tests/ui/racepos_n.sh по экспорту Scrooby)
// Красный (racepos_n.sh): -DUI_POS_RACERS_OLD=1 — прежнее «1» без «/2»
#include <stdio.h>
#include <string.h>
#include "ui_anim.h"
int main(void) {
  int fails = 0; char b[16];
  const int rivals = 1;   // S-M-R-T (m1): AddStageVehicle skinn_v — один соперник
  for (int pos = 1; pos <= 2; pos++) {
    uiPosText(b, sizeof b, pos, rivals + 1); char want[8]; snprintf(want, sizeof want, "%d /2", pos);
    int ok = !strcmp(b, want); fails += !ok;
    printf("CHECK pos %s  место %d, соперников %d: «%s» (PS2: «%s» + надстрочное st/nd)\n", ok ? "OK  " : "FAIL", pos, rivals, b, want);
  }
  uiPosText(b, sizeof b, 1, 0); int ok = !strcmp(b, "1"); fails += !ok;   // не гонка / без соперников — одна цифра
  printf("CHECK none %s  без числа участников: «%s»\n", ok ? "OK  " : "FAIL", b);
  printf("RESULT %s\n", fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}
