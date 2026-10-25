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
// Б TEST57 (тур с PSP: L5 (−201; −503), машина стоит, а игра грузит и выгружает 35–48 клеток в секунду; REGPRE мигает каждые 0,25 с = MEM_CHECK_US): регионы впрок брались при свободной куче >= MEM_RESERVE + 4 МБ
// и отдавались, как только свободное падало ниже той же границы — а свободное падает от самих загруженных регионов (≈1,3 МБ), и при куче около 7 МБ (L5 после №912: 6,6–7,9) условие
// гуляло туда-обратно. Теперь вход как раньше (запас 4 МБ), а уже взятые регионы держатся, пока свободно >= MEM_RESERVE + REGPRE_KEEP_MB (память всё равно не в обрезе: ниже MEM_RESERVE
// включается memTight и отдача далёких клеток), после вынужденного выхода повторный вход не раньше REGPRE_MEM_LOCK_S с. REGPRE_MEM_OLD=1 / «flag regprememold 1» — прежнее.
// Правило для семейства: решение «взять впрок» не должно зависеть от свободной памяти, которую само же решение меняет, без зазора больше размера взятого.
#ifndef REGPRE_MEM_OLD
#define REGPRE_MEM_OLD 0
#endif
#ifndef REGPRE_KEEP_MB
#define REGPRE_KEEP_MB 1u
#endif
#ifndef REGPRE_MEM_LOCK_S
#define REGPRE_MEM_LOCK_S 4.f
#endif
// fr — свободно, байт (~0u — не измерено); reserve — MEM_RESERVE; was — регионы впрок были взяты в прошлом кадре; lockT — момент вынужденного выхода (0 — не было), меняется здесь; old — прежнее условие
static int regPreMemOk(unsigned fr, unsigned reserve, int was, unsigned now, unsigned *lockT, int old) {
  if (fr == ~0u) return 1;
  if (old) return fr >= reserve + (4u << 20);
  if (was) { if (fr >= reserve + (REGPRE_KEEP_MB << 20)) return 1; *lockT = now | 1u; return 0; }
  if (*lockT && now - *lockT < (unsigned)(REGPRE_MEM_LOCK_S * 1e6f)) return 0;
  return fr >= reserve + (4u << 20);
}
#endif
