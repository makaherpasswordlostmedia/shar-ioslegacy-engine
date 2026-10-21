// Условие «регион ворот читать впрок» (main_stream.h): вход как раньше, выход с гистерезисом (аудит TEST26 16.10: мигание REGPRE на первой ходьбе из гаража).
// Чистая функция без движка — её гоняет хост-гейт tests/levels/regpre_unit.sh (красный: hyst = 0, прежнее поведение).
#ifndef REGPRE_H
#define REGPRE_H
#include <math.h>
#ifndef ZG_MAX
#define ZG_MAX 64
#endif
#ifndef GATE_PRE_M
#define GATE_PRE_M 90.f
#endif
#ifndef REGPRE_HOLD_S
#define REGPRE_HOLD_S 4.f
#endif
#ifndef REGPRE_OUT_M
#define REGPRE_OUT_M 40.f
#endif
static unsigned regPreT[ZG_MAX];   // момент последнего «да» по воротам i (0 — не было)
// dx,dz — от игрока к центру ворот; dirx,dirz — единичное направление хода; spd — м/с; now — мкс; hyst — 0: прежнее условие без удержания
static int regPreYes(int i, float dx, float dz, float dirx, float dirz, float spd, unsigned now, int hyst) {
  float d = sqrtf(dx * dx + dz * dz);
  int yes = d < GATE_PRE_M && (d < 30.f || (spd >= 4.f && (dx * dirx + dz * dirz) > .3f * d));   // рядом, либо впереди по ходу
  if (i < 0 || i >= ZG_MAX) return yes;
  if (yes) regPreT[i] = now | 1u;
  else if (hyst && regPreT[i] && now - regPreT[i] < (unsigned)(REGPRE_HOLD_S * 1e6f) && d < GATE_PRE_M + REGPRE_OUT_M) yes = 1;   // держим: ещё не вышел за запас
  else regPreT[i] = 0;
  return yes;
}
#endif
