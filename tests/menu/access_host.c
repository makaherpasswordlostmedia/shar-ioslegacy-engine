// Хост-гейт пункта ДОБИВКИ 26 (доступ к пунктам паузы и галерее будки): viewer/menu_access.h против записей PS2
// ~/Downloads/shar-psp-ps2-w/build/twins/o4/ps2_access_pause, ps2_access_options_unlock, ps2_access_settings_unlock,
// ps2_v105_booth_access (факт knowledge/facts/ps2-menu-access.yaml). Запуск — tests/menu/access.sh (зелёный + три красных).
#include <stdio.h>
#include <string.h>
#include "../../viewer/menu_access.h"

static int bad;
static void check(const char *group, const char *n, int ok) { printf("CHECK %s %s %s\n", group, n, ok ? "PASS" : "FAIL"); bad += !ok; }

// пауза: строки PauseSunday.pag порта (ui.h UI_P_*), RESET CAR скрыт (правка 137); шаг курсора как ui.c menuStep
enum { P_CONTINUE, P_RESET, P_MS, P_LP, P_VC, P_OPT, P_SAVE, P_QUIT, P_N };
static int step(unsigned skip, int from, int dir) {
  for (int k = 1; k <= P_N; k++) { int i = ((from + dir * k) % P_N + P_N) % P_N; if (!(skip >> i & 1)) return i; }
  return from;
}

int main(void) {
  // --- 1. MISSION SELECT. Уровень 1 диска: 8 сюжетных миссий m0..m7 (m0 The Cola Caper), на экране — 7 последних
  int story[8]; for (int i = 0; i < 8; i++) story[i] = i;
  // ps2_access_pause shot_80/120: новая игра, m0sd.0 «TALK TO MARGE» — пройденных 0, текущая m0 -> серый
  int msL1 = menuAccessMissionSelect(story, 8, 0u, 0, 1);
  check("ms", "L1_m0sd_new_game_dimmed", msL1 == 0);
  // ps2_access_options_unlock shot_150: ↓↓↓ + ✕ из CONTINUE = OPTIONS (SOUND / SETTINGS) — серый пункт курсор обходит
  unsigned skip = (1u << P_RESET) | (msL1 ? 0u : 1u << P_MS);
  int sel = P_CONTINUE; for (int k = 0; k < 3; k++) sel = step(skip, sel, 1);
  check("ms", "down3_from_CONTINUE_is_OPTIONS", sel == P_OPT);
  // соседние варианты (правило порта: то же условие, что у списка MISSION SELECT)
  check("ms", "L1_current_m1_open", menuAccessMissionSelect(story, 8, 1u, 1, 1) == 1);
  check("ms", "L1_done_m3_open", menuAccessMissionSelect(story, 8, 1u << 3, -1, 1) == 1);
  check("ms", "L2_first_story_open", menuAccessMissionSelect(story, 7, 0u, 0, 1) == 1);   // у L2 7 сюжетных — первая в списке
  check("ms", "no_story_dimmed", menuAccessMissionSelect(story, 0, 0u, -1, 1) == 0);
  // запасной список (msn_view.c mvMissionSelect !selRows: нет pextra.shr / uimsselold на L2+) — все пройденные и текущая сюжетная:
  // на том же L1 m0sd список открылся бы с The Cola Caper, значит пункт не серый; без текущей и пройденных — серый
  check("ms", "fallback_L1_m0sd_list_open", menuAccessMissionSelect(story, 8, 0u, 0, 0) == 1);
  check("ms", "fallback_nothing_dimmed", menuAccessMissionSelect(story, 8, 0u, -1, 0) == 0);

  // --- 2. START на OPTIONS / SETTINGS паузы -> игра (ps2_access_settings_unlock: START кадр 340, кадр 400 — HUD без паузы)
  const unsigned START = 0x8, CROSS = 0x4000, CIRCLE = 0x2000;   // pspctrl.h
  check("start", "START_closes_pause_from_SETTINGS", menuAccessSubStart(START, START) == 1);
  check("start", "CROSS_CIRCLE_are_not_START", menuAccessSubStart(CROSS | CIRCLE, START) == 0);

  // --- 3. будка L1: build/phonecars.txt порта (rewards.mfk + AddVehicleSelectInfo) и quest из каталога уровня (shop)
  const char *nm[8] = {"famil_v", "cletu_v", "elect_v", "plowk_v", "cDuff", "cVan", "snake_v", "wiggu_v"};
  const char *q[8] = {"defaultcar", "bonusmission", "streetrace", "forsale", "forsale", "forsale", 0, 0};
  int rank[8], ord[8];
  for (int k = 0; k < 8; k++) rank[k] = boothQuestRank(q[k]);
  int m = boothOrder(8, rank, ord);
  // PS2 shot_50..300: Family Sedan -> Electaurus -> Pickup Truck -> Plow King -> Duff Truck -> Surveillance Van -> Family Sedan
  const char *ps2[6] = {"famil_v", "elect_v", "cletu_v", "plowk_v", "cDuff", "cVan"};
  int same = m == 6; for (int k = 0; same && k < 6; k++) same = !strcmp(nm[ord[k]], ps2[k]);
  char got[160] = ""; for (int k = 0; k < m; k++) { strcat(got, k ? "," : ""); strcat(got, nm[ord[k]]); }
  printf("BOOTH order %s\n", got);
  check("booth", "L1_six_rows_PS2_order", same);
  check("booth", "locked_shows_stars", boothShowStats(0) == 1 && boothShowStats(1) == 1);
  check("booth", "locked_no_Accept_owned_Accept", boothShowAccept(0) == 0 && boothShowAccept(1) == 1);
  // машины не из каталога уровня (AddVehicleSelectInfo snake_v, wiggu_v) в галерее нет — принадлежность порт хранит по каталогу
  // уровня, своей такую машину phone_view.c owned() не видит (menu_access.h п. 3; на PS2 машины прошлых уровней не сняты)
  int foreign = 0; for (int k = 0; k < m; k++) foreign |= rank[ord[k]] == BOOTH_Q_NONE;
  check("booth", "no_foreign_cars", !foreign);

  printf("RESULT failures=%d\n", bad); return bad ? 1 : 0;
}
