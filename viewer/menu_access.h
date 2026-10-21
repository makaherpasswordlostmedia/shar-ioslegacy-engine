// menu_access.h — доступ к пунктам паузы и галереи будки по записям PS2 (пункт ДОБИВКИ 26, факт knowledge/facts/ps2-menu-access.yaml).
// Чистые функции без состояния: движок (main.c, msn_view.c, phone_view.c) и хост-гейт tests/menu/access_host.c зовут одно и то же.
// Записи наблюдателя (~/Downloads/shar-psp-ps2-w/build/twins/o4/, только чтение):
//   ps2_access_pause          — новая игра L1, этап m0sd.0 «TALK TO MARGE» (миссия m0 The Cola Caper), в машине: START ->
//                               PAUSE MENU: CONTINUE, MISSION SELECT (серый), LEVEL PROGRESS, VIEW CARDS, OPTIONS, SAVE GAME, QUIT GAME
//   ps2_access_options_unlock — из той же паузы ↓↓↓ + ✕ = OPTIONS (SOUND / SETTINGS): серый MISSION SELECT курсор обходит
//   ps2_access_settings_unlock— ↓ + ✕ = SETTINGS; START из SETTINGS (кадр 340) -> сразу игра (кадр 400: HUD, паузы нет)
//   ps2_v105_booth_access     — будка L1 той же игры: ► по кругу Family Sedan -> Electaurus -> Pickup Truck -> Plow King ->
//                               Duff Truck -> Surveillance Van -> Family Sedan (6 строк); у закрытых звёзды есть, подсказка
//                               только Back; у открытой Family Sedan — «Damaged: 0 %», Accept и Back
#ifndef MENU_ACCESS_H
#define MENU_ACCESS_H

// 1. MISSION SELECT паузы серый и пропускается курсором, когда на экране MissionSelect.scr нечего выбрать: ни одна из 7 последних
//    сюжетных миссий уровня (строки MissionSelect.pag; у L1 The Cola Caper в список не входит) не пройдена и не текущая.
//    [PS2 ps2_access_pause shot_80/120] L1 m0sd.0, пройденных 0, текущая m0 — серый; ↓↓↓ из CONTINUE = OPTIONS (обход).
//    Обобщение на прочие состояния (пройдена хоть одна строка / текущая строка) — ПРАВИЛО ПОРТА: то же условие, по которому
//    список и так открывался (msn_view.c mvMissionSelect), в обоих его режимах: rows=1 — экран MissionSelect.scr (pextra.shr, 7
//    последних сюжетных), rows=0 — запасной список без экрана (нет pextra.shr или служебное uimsselold на L2+): все пройденные
//    сюжетные и текущая. Прежнее (=1): пункт всегда белый, ✕ по нему ничего не открывал.
#ifndef PAUSE_MS_DIM_OLD
#define PAUSE_MS_DIM_OLD 0
#endif
// story[0..ns) — индексы сюжетных миссий уровня по порядку, completed — маска пройденных, cur — текущая сюжетная (-1 — нет),
// rows — режим списка (1 — строки экрана MissionSelect.scr, 0 — запасной список msn_view.c mvMissionSelect !selRows)
static inline int menuAccessMissionSelect(const int *story, int ns, unsigned completed, int cur, int rows) {
#if PAUSE_MS_DIM_OLD
  (void)story; (void)ns; (void)completed; (void)cur; (void)rows; return 1;
#else
  for (int i = rows ? ns - 7 : 0; i < ns; i++) {
    if (i < 0 || !story) continue;
    int m = story[i];
    if ((m >= 0 && m < 32 && (completed >> m & 1u)) || m == cur) return 1;
  }
  return 0;
#endif
}

// 2. START на экранах OPTIONS паузы (pmenu.shr: OPTIONS, SOUND, SETTINGS) закрывает паузу целиком — сразу в игру.
//    [PS2 ps2_access_settings_unlock: START на кадре 340 из SETTINGS, кадр 400 — игра с HUD; на страницах подсказка
//    «Press START button to Continue»]. SOUND в записи не открывали — та же подсказка страницы, ПРАВИЛО ПОРТА: как OPTIONS/SETTINGS.
//    Прежнее (=1): START на этих экранах ничего не делал.
#ifndef PAUSE_SUB_START_OLD
#define PAUSE_SUB_START_OLD 0
#endif
static inline int menuAccessSubStart(unsigned hit, unsigned startBit) {
#if PAUSE_SUB_START_OLD
  (void)hit; (void)startBit; return 0;
#else
  return (hit & startBit) != 0;
#endif
}

// 3. Галерея будки. [PS2 ps2_v105_booth_access shot_50..400] L1: 6 строк — машины-награды уровня, порядок defaultcar, streetrace,
//    bonusmission, forsale (по rewards.mfk внутри типа): Family Sedan, Electaurus, Pickup Truck, Plow King, Duff Truck,
//    Surveillance Van. Машин AddVehicleSelectInfo (snake_v, wiggu_v — награды L5/L6) в галерее L1 нет. Закрытая: замок, «LEVEL 1»,
//    звёзды видны, подсказка только Back (Accept нет). Открытая: звёзды, Accept и Back.
//    Порядок типов на других уровнях — ПРАВИЛО ПОРТА: та же раскладка rewards.mfk (defaultcar, bonusmission, streetrace, forsale×3)
//    у всех семи уровней. Машины не из каталога уровня (AddVehicleSelectInfo, награды других уровней) в галерею не входят вовсе,
//    полученные или нет: принадлежность в порту хранится по каталогу уровня (shop.c Coins.owned[level]), машину другого уровня
//    phone_view.c owned() своей не видит. Есть ли на PS2 в будке машины, выигранные на прошлых уровнях, — не снято (открыто).
//    Прежнее (=1): список build/phonecars.txt как есть (8 строк у L1, cletu_v перед elect_v, snake_v/wiggu_v всегда закрыты),
//    у закрытой звёзд нет, Accept всегда.
#ifndef BOOTH_ACCESS_OLD
#define BOOTH_ACCESS_OLD 0
#endif
enum { BOOTH_Q_DEFAULT = 0, BOOTH_Q_STREETRACE, BOOTH_Q_BONUS, BOOTH_Q_FORSALE, BOOTH_Q_OTHER, BOOTH_Q_NONE };
static inline int boothQuestRank(const char *q) {   // quest из BindReward (shop.h ShopItem.quest); NULL — машины нет в каталоге уровня
  if (!q) return BOOTH_Q_NONE;
  const char *t[4] = {"defaultcar", "streetrace", "bonusmission", "forsale"};
  for (int r = 0; r < 4; r++) { const char *a = q, *b = t[r]; while (*a && *a == *b) { a++; b++; } if (!*a && !*b) return r; }
  return BOOTH_Q_OTHER;
}
// rank[k] — boothQuestRank строки k списка -> ord[0..m) номера строк в порядке показа, m
static inline int boothOrder(int n, const int *rank, int *ord) {
  int m = 0;
#if BOOTH_ACCESS_OLD
  (void)rank; for (int k = 0; k < n; k++) ord[m++] = k;
#else
  for (int r = BOOTH_Q_DEFAULT; r < BOOTH_Q_NONE; r++)   // BOOTH_Q_NONE (не из каталога уровня) — в галерее нет
    for (int k = 0; k < n; k++) if (rank[k] == r) ord[m++] = k;
#endif
  return m;
}
static inline int boothShowStats(int owned) {
#if BOOTH_ACCESS_OLD
  return owned;
#else
  (void)owned; return 1;
#endif
}
static inline int boothShowAccept(int owned) {
#if BOOTH_ACCESS_OLD
  (void)owned; return 1;
#else
  return owned;
#endif
}
#endif
