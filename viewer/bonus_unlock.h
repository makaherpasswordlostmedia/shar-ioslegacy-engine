// Правка Роба 421 (09.10): открытие трасс бонус-игры (Super Sprint, трассы b01..b07 = уровни 1..7) как в оригинале.
// Чистый C99 без PSP-заголовков: один код для EBOOT (viewer/main.c, viewer/bonus_play.h, родные экраны MiniMenu) и проверки на Маке
// (tests/bonus/unlock_host.c). ОДНА ПРАВДА: «трасса N открыта?» спрашивают только здесь (bonusTrackOpen по маске bonusUnlockMask).
//
// ДАННЫЕ (запись PS2 наблюдателя, knowledge/facts ps2-bonus-native-access; записи o4/ps2_bonus_main_selection, ps2_bonus_card17_access,
// ps2_bonus_minimenu_entry): в исходном меню BONUS GAME серый, Cross не входит; после 7/7 карточек уровня 1 (кадр 250) — «LEVEL CARDS
// COLLECTED! / New bonus game track unlocked!» (Hud.pag ItemsComplete + ItemsUnlocked), пункт BONUS GAME жёлтый, в MiniMenu активна
// только первая трасса, остальные 6 затемнены. Карточек на уровень 7: collect-l1..l7.shr (ncard = 7, номера N1..N7), HUD «7/7».
// ПРАВИЛО: трасса N открыта, когда собраны ВСЕ карточки уровня N (маска уровня = 0x7F, collect.h: бит k-1 — карточка cardNk).
// Роб помнил «по трём гонкам уровня»; запись PS2 показывает открытие по карточкам — сделано по записи.
// DEV SAVE (правки 335/350): полное прохождение — карточки всех 7 уровней собраны (bonusDevCards) -> открыты все 7 трасс.
// BONUS_UNLOCK_OLD=1 — как было до 421: все 7 трасс открыты, пункт BONUS GAME доступен по наличию файлов трасс
// (красный контроль гейта tests/bonus/unlock.sh).
#ifndef SHAR_BONUS_UNLOCK_H
#define SHAR_BONUS_UNLOCK_H

#ifndef BONUS_UNLOCK_OLD
#define BONUS_UNLOCK_OLD 0
#endif
#define BONUS_TRACKS 7
#define BONUS_ALL_TRACKS ((1u << BONUS_TRACKS) - 1u)
#define BONUS_LEVEL_CARDS 0x7Fu   // все 7 карточек уровня (collect-l<N>.shr: ncard 7)

// cards[L] (L = 1..7) — маска собранных карточек уровня L (Collect.st.cards / SaveGame.cards) -> бит N-1: трасса N открыта
static inline unsigned bonusUnlockMask(const unsigned char *cards) {
  if (BONUS_UNLOCK_OLD) return BONUS_ALL_TRACKS;
  unsigned m = 0;
  for (int n = 1; n <= BONUS_TRACKS; n++) if (cards && (cards[n] & BONUS_LEVEL_CARDS) == BONUS_LEVEL_CARDS) m |= 1u << (n - 1);
  return m;
}
static inline int bonusTrackOpen(unsigned mask, int track) { return track >= 1 && track <= BONUS_TRACKS && (mask >> (track - 1) & 1u); }
// выбор ◄ ►: следующая открытая трасса в сторону d (по кругу); закрытые пропускаются; других открытых нет — та же
static inline int bonusTrackStep(unsigned mask, int track, int d) {
  for (int k = 1; k <= BONUS_TRACKS; k++) {
    int t = ((track - 1 + d * k) % BONUS_TRACKS + BONUS_TRACKS) % BONUS_TRACKS + 1;
    if (bonusTrackOpen(mask, t)) return t;
  }
  return track;
}
// трасса выбора при входе: прежняя, если открыта, иначе первая открытая (ни одной — 1)
static inline int bonusTrackPick(unsigned mask, int track) {
  if (bonusTrackOpen(mask, track)) return track;
  for (int t = 1; t <= BONUS_TRACKS; t++) if (bonusTrackOpen(mask, t)) return t;
  return 1;
}
// DEV SAVE: карточки всех 7 уровней собраны
static inline void bonusDevCards(unsigned char *cards) { for (int n = 1; n <= BONUS_TRACKS; n++) cards[n] |= (unsigned char)BONUS_LEVEL_CARDS; }

#endif
