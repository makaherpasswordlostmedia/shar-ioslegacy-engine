// Подсказки обучения Барта (viewer/tutorial.h). Данные: строки TUTORIAL_NNN библии в ui.shr (экран Tutorial.scr, tools/ui_export.py),
// реплики — дорожки music.sap (tools/sound_export.py TUT_VOICES). Что к чему — таблица ниже, сверено с записью PS2: текст на экране
// и расшифровка звука в тот же момент (tools/ps2ref/CATALOG_L1.md). «Continue» — когда реплики кончились (запись: 17:06, 2:27).
#include <stdio.h>
#include <string.h>
#include <pspctrl.h>
#include "tutorial.h"
#include "ui.h"
#include "ui_anim.h"   // №516: кривые появления и ухода подсказки
#include "sound.h"
#include "audio.h"

static const struct { int msg; const char *voice[2]; const char *name; } TUT[TUT_COUNT] = {
  [TUT_WALK]      = {2,  {"v_startps2_1_tu_brt_l1t1"},    "walk"},       // 1:05 USE + OR LEFT ANALOG STICK TO MOVE AROUND / £ / ®
  [TUT_GETIN]     = {4,  {"v_incarps2_1_tu_brt_l1t1"},    "getin"},      // 1:45 PRESS @ TO GET INTO CAR
  [TUT_GAS]       = {3,  {"v_driveps2_1_tu_brt_l1t1"},    "gas"},        // 1:50 PRESS ¿ TO ACCELERATE / µ BRAKE / § HANDBRAKE
  [TUT_BREAK]     = {12, {"v_broken_1_tu_brt_l1t1"},      "break"},      // 2:22 BREAK CERTAIN OBJECTS TO GET COINS («That's the stuff, Psycho!»)
  [TUT_COINS]     = {8,  {"v_coin_1_tu_hom_l1t1", "v_coin_2_tu_brt_l1t1"}, "coins"},   // 2:29 USE COINS TO PURCHASE CARS AND CLOTHES
  [TUT_INSIDE]    = {13, {"v_interiorps2_1_tu_brt_l1t1"}, "inside"},     // 2:55 PRESS @ TO GO INSIDE
  [TUT_WRENCH]    = {17, {"v_wrench_1_tu_brt_l1t1"},      "wrench"},     // 4:15 USE WRENCHES TO FIX YOUR CAR (подобран ключ)
  [TUT_WASP]      = {0,  {"v_camera_1_tu_brt_l1t1"},      "wasp"},       // 11:20 TO DESTROY WASP CAMERAS, JUMP ... § TO KICK THE WASP
  [TUT_RACE]      = {6,  {"v_race_1_tu_brt_l1t1"},        "race"},       // 16:55 WIN ALL RACES TO GET A CAR
  [TUT_BONUS]     = {1,  {"v_bonus_1_tu_brt_l1t1"},       "bonus"},      // 22:55 BONUS MISSION
  [TUT_DESTROYED] = {15, {"v_damaged_1_tu_brt_l1t1"},     "destroyed"},  // 33:36 VEHICLE DESTROYED! FIND A WRENCH, OR GO TO A PHONEBOOTH
  [TUT_CARD]      = {7,  {"v_card_1_tu_brt_l1t1"},        "card"},       // FIND ALL CARDS TO GET A SURPRISE (правило порта)
  [TUT_GAG]       = {5,  {"v_gag_1_tu_brt_l1t1"},         "gag"},        // FIND ALL GAGS (правило порта)
  [TUT_TIMETRIAL] = {20, {"v_timetrial_1_tu_brt_l1t1"},   "timetrial"},  // WIN THE TIME TRIAL RACE TO EARN EXTRA COINS (правило порта)
  [TUT_UNLOCKED]  = {16, {"v_rewardps2_1_tu_brt_l1t1"},   "unlocked"},   // 14:17 UNLOCKED CAR / GO TO PHONE BOOTH TO ACCESS THIS VEHICLE AT ANY TIME
  [TUT_PHONE]     = {9,  {0},                             "phone"},      // PRESS @ TO USE TELEPHONE BOOTH. (TUTORIAL_009; реплики Барта на диске нет — текст, правило порта: у будки)
};
// подсказки «рядом с …» (машина, дверь, значок гонки / бонуса / заезда, ходьба) повторяются каждый кадр, пока условие есть
#define NEAR_MASK (1u << TUT_WALK | 1u << TUT_GETIN | 1u << TUT_INSIDE | 1u << TUT_RACE | 1u << TUT_BONUS | 1u << TUT_TIMETRIAL | 1u << TUT_PHONE)
#define TUT_NOVOICE_S 2.f   // нет реплики (пакета звука нет): Continue через столько секунд — правило порта
#define TUT_MIN_S .6f       // Continue не раньше: случайное X сразу после события не закрывает подсказку — правило порта
#define TUT_GAP_S .5f       // между подсказками подряд (запись 2:27 -> 2:29: «ломай» закрыта, через миг — монеты) — правило порта

static int forceMsg = -1;   // служебное «flag tutmsg N» (правка 267): показать строку N библии, -1 — нет
static int levelOn, userOn = 1, cur = -1, noVoice, vi, voiceT = -1, savedMode = -1, anyVoice, busy;
static unsigned shown, queued;
static float t, gap, later[TUT_COUNT];
#ifndef TUT_EXIT_OLD
#define TUT_EXIT_OLD 0   // 1 — счёт ухода пузыря в tutTick, как до ревизии 3.1
#endif
static int exitMsg = -1, exitCont; static float exitT;   // №516: уход подсказки обратным масштабом (ui_anim.h 2г)
static void (*logFn)(const char *);
static void logf2(const char *what) {
  if (!logFn || cur < 0) return;
  char s[128]; snprintf(s, sizeof s, "TUTORIAL %s ev=%s msg=%d voice=%d t=%.1f\n", what, TUT[cur].name, TUT[cur].msg, voiceT, t);
  logFn(s);
}
static int voiceNext(void) {   // следующая реплика подсказки (монеты: Гомер, потом Барт); 0 — реплик больше нет
  while (vi < 2 && TUT[cur].voice[vi]) {
    const char *nm = TUT[cur].voice[vi++]; int tr = noVoice ? -1 : audioTrack(nm);
    if (tr >= 0) { voiceT = tr; anyVoice = 1; sndVoice(tr); return 1; }
  }
  voiceT = -1; return 0;
}
static int canContinue(void) {
  if (t < TUT_MIN_S) return 0;
  if (voiceT >= 0) return !sndVoicePlaying(voiceT) && !voiceNext();
  return anyVoice || t >= TUT_NOVOICE_S;   // реплик нет (пакета звука нет) — Continue через TUT_NOVOICE_S
}
static void startExit(int cont) {   // №516: пузырь уходит обратным масштабом поверх кадра игры (запись PS2 262,9 с)
  if (TUT_ANIM_OLD || cur < 0 || forceMsg >= 0) return;
  exitMsg = TUT[cur].msg; exitCont = cont; exitT = 0.f;
}
static void closeTut(void) {
  if (voiceT >= 0 && sndVoicePlaying(voiceT)) sndVoice(-1);
  voiceT = -1; cur = -1; gap = TUT_GAP_S;
  if (savedMode >= 0) { sndMode(savedMode); savedMode = -1; }
}
void tutSetLog(void (*log)(const char *)) { logFn = log; }
void tutReset(int levelMode) {
  if (cur >= 0) closeTut();
  if (!TUT_EXIT_OLD) exitMsg = -1;   // ревизия 3.1: после смены уровня / новой игры пузырь не едет за игроком
  levelOn = levelMode; cur = -1; shown = queued = 0; t = gap = 0.f; memset(later, 0, sizeof later);
}
void tutSetBusy(int b) { busy = b; }
void tutSetUser(int on) { userOn = on != 0; if (!userOn) queued = 0; }
int tutUser(void) { return userOn; }
unsigned tutShown(void) { return shown; }
void tutSetShown(unsigned m) { shown = m; queued &= ~m; }
int tutActive(void) { return cur >= 0 || forceMsg >= 0; }
void tutService(const char *flag, float a) {   // служебное (гейт tests/ui/tutorial.sh)
  if (!strcmp(flag, "tutnovoice")) noVoice = 1;
  else if (!strcmp(flag, "tutvoice")) noVoice = 0;
  else if (!strcmp(flag, "tutagain") && a >= 0.f && a < TUT_COUNT) shown &= ~(1u << (int)a);   // подсказку ev снова можно показать
  else if (!strcmp(flag, "tutmsg")) forceMsg = a >= 0.f ? (int)a : -1;   // правка 267: строка TUTORIAL_NNN на экране (гейт раскладки)
  else if (!strcmp(flag, "tutold")) uiTutLayoutOld(a != 0.f);           // правка 267: прежняя раскладка (красный контроль)
}
static int ready(int ev) { return ev >= 0 && ev < TUT_COUNT && levelOn && userOn && !(shown >> ev & 1u) && uiTutorialCount() > TUT[ev].msg; }
int tutPending(int ev) { return ready(ev); }
static void show(int ev) {
  cur = ev; shown |= 1u << ev; queued &= ~(1u << ev); t = 0.f; vi = 0; voiceT = -1; anyVoice = 0;
  if (savedMode < 0) { savedMode = sndModeCur(); sndMode(SND_MODE_MISSIONSCREEN); }   // тюнер «MissionScreen» (global.spt): только голос
  voiceNext();
  logf2("on");
}
void tutEvent(int ev) {
  if (!ready(ev)) return;
  if (cur >= 0 || gap > 0.f || busy) {   // подсказка на экране (или разговор): событие — следующей (монеты после «ломай», 2:29);
    if (!(NEAR_MASK >> ev & 1u)) queued |= 1u << ev;   // «рядом с …» не копится — придёт само, пока игрок там
    return;
  }
  show(ev);
}
void tutEventIn(int ev, float sec) { if (ready(ev) && later[ev] <= 0.f) later[ev] = sec > .01f ? sec : .01f; }
void tutTick(float dt) {
  if (TUT_EXIT_OLD && exitMsg >= 0) { exitT += dt; float k; if (!uiTutExitScale(exitT, &k)) exitMsg = -1; }   // №516: счёт ухода (игровое время: пауза его стоит)
  if (cur >= 0 || busy) return;
  if (gap > 0.f) { gap -= dt; if (gap > 0.f) return; gap = 0.f; }
  for (int e = 0; e < TUT_COUNT; e++) if (later[e] > 0.f && (later[e] -= dt) <= 0.f) { later[e] = 0.f; tutEvent(e); }
  for (int e = 0; e < TUT_COUNT && cur < 0; e++) if (queued >> e & 1u) { queued &= ~(1u << e); if (ready(e)) show(e); }
}
int tutInput(unsigned hit, float wallDt, int *disabled) {
  if (disabled) *disabled = 0;
  if (cur < 0) return 0;
  t += wallDt;
  if (hit & PSP_CTRL_SQUARE) {   // «Disable Tutorials»: подсказка закрыта, дальше не показываются (строка Tutorial в Settings)
    logf2("disable"); userOn = 0; queued = 0; memset(later, 0, sizeof later); if (disabled) *disabled = 1;
    startExit(0);
    closeTut(); uiPopHookFire(UI_EV_BACK); return 1;
  }
  if ((hit & PSP_CTRL_CROSS) && canContinue()) { logf2("off"); startExit(1); closeTut(); uiPopHookFire(UI_EV_ACCEPT); return 1; }
  return 0;
}
int tutDraw(void) {
  if (forceMsg >= 0) return uiDrawTutorial(forceMsg, 1);
  if (cur < 0) return 0;
  if (!TUT_ANIM_OLD) uiTutorialScale(uiTutEnterScale(t));   // №516: рост из центра экрана 0,56 → 1,0 за 4 шага по 1/30 с
  int r = uiDrawTutorial(TUT[cur].msg, canContinue());
  uiTutorialScale(1.f); return r;
}
int tutDrawExit(float wallDt) {   // №516: после закрытия; 0 — уходить нечему
  // ревизия 3.1: счёт ухода шёл только в tutTick, а тот зовут под условием «свободен и не в комнате»; беседа или переход в первые 4 кадра — пузырь висел поверх HUD.
  // Теперь тот же счёт ведёт рисование (wallDt: пауза рисование глушит, не считается). TUT_EXIT_OLD=1 — прежнее
  if (!TUT_EXIT_OLD && exitMsg >= 0) { exitT += wallDt; float k0; if (!uiTutExitScale(exitT, &k0)) exitMsg = -1; }
  float k; if (exitMsg < 0 || !uiTutExitScale(exitT, &k)) return 0;
  uiTutorialScale(k); int r = uiDrawTutorial(exitMsg, exitCont); uiTutorialScale(1.f); return r;
}
