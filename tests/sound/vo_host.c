// Гейт реплик аудита 09.10 п. 12/58 (герой и соперники): настоящий микшер порта (viewer/sound.c + audio.c, AUDIO_HOST) с пакетом
// звука уровня 1. Мак, CPU, без эмулятора.
//   pack  — в пакете столько дорожек семейства, сколько ресурсов у диска (dialog.spt): W_Card/Mvic/Mfail/Springboard/Fall/NewAI/
//           Pass/Passed водителя уровня (Hom) и V_Mvic/Mfail/Damage/Tail соперников уровня (Skn/Skin, Smi); числа диска даёт
//           tests/sound/vo_check.sh (счёт по dialog.spt) аргументами
//   say   — sndSay(событие, 1) запускает дорожку своего семейства, и она слышна: RMS шины голоса за 1,5 с громче −45 dBFS
//   rival — sndRivalSay(водитель, вид, 1): skinner -> v_*_skn_/skin_, smithers -> v_*_smi_; bart, jasper — без реплик (0)
//   host PACKDIR/ "w_card=5 w_mvic=8 …"   код 0 — все проверки прошли
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "sound.h"
#include "audio.h"

#define FR 512
static const char *pack; static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-6s %s  %s\n", n, ok ? "OK  " : "FAIL", d); fails += !ok; }
static double voiceDb(float sec) {
  static short b[FR * 2]; double e = 0; long c = 0; int n = (int)(sec * 44100 / FR) * FR;
  for (int k = 0; k < n; k += FR) { audioHostMix(b, FR); for (int i = 0; i < FR * 2; i++) { double x = b[i] / 32768.0; e += x * x; c++; } }
  return 20 * log10(sqrt(e / (c ? c : 1)) + 1e-12);
}
static void begin(void) {
  if (sndInit(pack) < 0) { printf("FAIL sndInit %s\n", sndError()); exit(2); }
  sndMode(SND_MODE_NORMAL); sndUserVolumes(0, 0, 0, 1);   // слышно только голос
  audioAmbience(-1, 0); audioListener(4000.f, 3.f, 4000.f, 1.f, 0.f);
  for (int i = 0; i < 24; i++) sndFrame(.25f, 4000.f, 3.f, 4000.f, 1.f, 0.f, 4000.f, 0.f, 4000.f);   // 6 с: пауза 5 с между репликами прошла
}
static int count(const char *pre) {
  int n = 0; for (int t = 0, nt = audioTrackCount(); t < nt; t++) if (audioTrackBus(t) == 2 && !strncmp(audioTrackName(t), pre, strlen(pre))) n++;
  return n;
}
int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: host PACKDIR/ \"w_card_hom_=5 …\"\n"); return 2; }
  pack = argv[1]; char d[256];
  // 1) пакет против диска
  begin();
  char spec[2048]; snprintf(spec, sizeof spec, "%s", argv[2]);
  for (char *tok = strtok(spec, " "); tok; tok = strtok(NULL, " ")) {
    char *eq = strchr(tok, '='); if (!eq) continue; *eq = 0; int want = atoi(eq + 1), got = count(tok);
    snprintf(d, sizeof d, "дорожек %s*: %d, у диска %d", tok, got, want); check("pack", got == want && want > 0, d);
  }
  sndShutdown();
  // 2) событие героя -> своё семейство, слышно
  static const int ev[] = {SND_SAY_CARD, SND_SAY_MVIC, SND_SAY_MFAIL, SND_SAY_SPRINGBOARD, SND_SAY_FALL, SND_SAY_NEWAI, SND_SAY_PASS, SND_SAY_PASSED, SND_SAY_HITBYC, SND_SAY_TAIL, SND_SAY_AIDESTROY, SND_SAY_TURBO, SND_SAY_DODGE};
  static const char *const key[] = {"w_card_", "w_mvic_", "w_mfail_", "w_springboard_", "w_fall_", "w_newai_", "w_pass_", "w_passed_", "w_hitbyc_", "w_tail_", "w_aidestroy_", "w_turbo_", "w_dodge_"};
  for (unsigned i = 0; i < sizeof ev / sizeof *ev; i++) {
    begin(); int ok = sndSay(ev[i], 1); const char *nm = ok ? sndSayLastName() : "-"; double db = ok ? voiceDb(1.5f) : -200.0;
    snprintf(d, sizeof d, "sndSay(%s): %s, голос %.1f dBFS", key[i], nm, db);
    check("say", ok && !strncmp(nm, key[i], strlen(key[i])) && db > -45.0, d); sndShutdown();
  }
  // 3) соперники
  static const struct { const char *drv; int kind; const char *pre[2]; } rv[] = {
    {"skinner", SND_V_MVIC, {"v_mvic_skn_", "v_mvic_skin_"}}, {"skinner", SND_V_MFAIL, {"v_mfail_skn_", "v_mfail_skin_"}},
    {"skinner", SND_V_HITCAR, {"v_hitcar_skn_", 0}}, {"skinner", SND_V_TAIL, {"v_tail_skn_", 0}}, {"smithers", SND_V_DAMAGE, {"v_damage_smi_", 0}}, {"smithers", SND_V_MVIC, {"v_mvic_smi_", 0}},
    {"bart", SND_V_MVIC, {0, 0}}, {"jasper", SND_V_DAMAGE, {0, 0}}};
  for (unsigned i = 0; i < sizeof rv / sizeof *rv; i++) {
    begin(); int ok = sndRivalSay(rv[i].drv, rv[i].kind, 1); const char *nm = ok ? sndSayLastName() : "-"; double db = ok ? voiceDb(1.5f) : -200.0;
    int good = rv[i].pre[0] ? ok && db > -45.0 && (!strncmp(nm, rv[i].pre[0], strlen(rv[i].pre[0])) || (rv[i].pre[1] && !strncmp(nm, rv[i].pre[1], strlen(rv[i].pre[1]))))
                            : !ok && !sndRivalHas(rv[i].drv);
    snprintf(d, sizeof d, "sndRivalSay(%s, %d): %s, голос %.1f dBFS (ждём %s)", rv[i].drv, rv[i].kind, nm, db, rv[i].pre[0] ? rv[i].pre[0] : "нет реплик");
    check("rival", good, d); sndShutdown();
  }
  for (int kind = 0; kind < SND_PED_KINDS; kind++) {
    static const char *pre[] = {"p_hitbyc_barney_", "p_nhitbyc_barney_", "p_hitbyw_barney_"};
    begin(); int ok = sndPedNamedSayAt(kind, "barney", 4000.f, 3.f, 4000.f);
    const char *nm = ok ? audioTrackName(audioStreamTrack(AUDIO_ST_DIALOG)) : "-";
    double db = ok ? voiceDb(1.5f) : -200.;
    snprintf(d, sizeof d, "barney kind=%d: %s %.1f dBFS", kind, nm, db);
    check("named", ok && !strncmp(nm, pre[kind], strlen(pre[kind])) && db > -45., d); sndShutdown();
  }
  // Centre/radius of the Quimby sphere, independently read from l1r3 locator:
  // (-169.8145, 3.65177, 105.980575), radius .75. No invented reach margin.
  begin(); int door = sndDoorbellNear(-169.8145f, 3.65177f, 105.980575f);
  int outside = sndDoorbellNear(-168.8145f, 3.65177f, 105.980575f);
  int bell = sndDoorbellSay(door); const char *bn = bell ? audioTrackName(audioStreamTrack(AUDIO_ST_DIALOG)) : "-";
  audioListener(-169.8145f, 3.65177f, 105.980575f, 1.f, 0.f);
  double db = bell ? voiceDb(1.5f) : -200.;
  snprintf(d, sizeof d, "Quimby centre=%d outside=%d: %s %.1f dBFS", door, outside, bn, db);
  check("door", door >= 0 && outside == -1 && bell && !strncmp(bn,"db_quimby_",10) && db > -45., d); sndShutdown();
  printf("RESULT %s (%d провалов)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
