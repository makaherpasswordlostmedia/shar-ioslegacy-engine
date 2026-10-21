// Правка 345 (атлас миссий 332): реплики водителя уровня на старте миссии и при выходе из машины, атмосфера комнат — тем же
// viewer/sound.c + viewer/audio.c (AUDIO_HOST), на настоящем звуковом пакете уровня (sfx.sab + music.sap, tools/sound_export.py).
// [PS2] своя pcsx2-twins без окна и звука, 05.10 (agent345/ps2): ✕ Continue карточки m0 -> через 3 кадра homer/w_mstart_hom_03
// (Continue на 420) или _04 (на 500) — 3 старта из 3; выход из машины -> через 6–8 кадров homer/w_goc_hom_legs / walk / horse —
// 5 выходов из 11; в Kwik-E-Mart — ambience/room_small_01 (атлас m0d).
//   pack   — в пакете семейства W_Mstart_<код>_* и W_GOC_<код>_* водителя уровня (код — аргумент), чужих водителей нет
//   mstart — sndSay(MSTART, 1) каждый раз даёт реплику водителя; за 24 старта — не меньше 3 разных, подряд не повторяется
//   goc    — 240 выходов (фронт sndGetOut): реплик 35–65 %, все W_GOC_ водителя, подряд не повторяется
//   room   — вход в комнату с атмосферой (аргумент ROOM) -> её дорожка (аргумент TRACK); комната без записи (Moes) — улица как была;
//            выход — снова атмосфера улицы, что звучала до входа; ходьба в комнате атмосферу не меняет
// Красный (tests/sound/pcsay.sh): --old (sndPcSayOld = sndRoomAmbOld = 1) и прежний пакет (без семейств и таблицы RAMB) обязаны упасть
//   pcsay_host PACKDIR/ CODE ROOM TRACK [--old]      CODE — hom / brt / lis / mrg / apu; ROOM "-" — комнат с атмосферой нет
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sound.h"
#include "audio.h"

static int fails;
static void check(const char *name, int ok, const char *d) { printf("CHECK %-6s %s  %s\n", name, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static short buf[512 * 2];
static void run(float sec, float px, float pz) {   // время идёт: сведение и кадр звука (поток реплики доигрывает)
  float dt = 512.f / 44100.f;
  for (float t = 0; t < sec; t += dt) { sndFrame(dt, px, 2.f, pz - 5.f, 0.f, 1.f, px, 0.f, pz); audioHostMix(buf, 512); }
}
static const char *amb(void) { SndStats s; sndStats(&s); return s.ambience; }

int main(int argc, char **argv) {
  if (argc < 5) { fprintf(stderr, "pcsay_host PACKDIR/ CODE ROOM TRACK [--old]\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  const char *code = argv[2], *room = argv[3], *track = argv[4];
  int old = 0, noGicSource = 0;
  for (int i = 5; i < argc; i++) {
    if (!strcmp(argv[i], "--old")) old = 1;
    else if (!strcmp(argv[i], "--no-gic-source")) noGicSource = 1;
    else { fprintf(stderr, "unknown option: %s\n", argv[i]); return 2; }
  }
  // Decision by Rob, 2026-10-09: Apu's entry voice is out of scope (V93).
  // This exception cannot suppress missing GIC resources for another hero.
  int apuEntryWaived = noGicSource && !strcmp(code, "apu");
  if (sndInit(argv[1]) < 0) { printf("FAIL: sndInit %s\n", sndError()); return 1; }
  sndPcSayOld = sndRoomAmbOld = old;
  char d[300], pm[24], pg[24], pi[24]; snprintf(pm, sizeof pm, "w_mstart_%s_", code); snprintf(pg, sizeof pg, "w_goc_%s_", code); snprintf(pi, sizeof pi, "w_gic_%s_", code);
  // pack
  int nm = 0, ng = 0, ni = 0, foreign = 0;
  for (int t = 0, n = audioTrackCount(); t < n; t++) {
    const char *nmz = audioTrackName(t);
    if (!strncmp(nmz, "w_mstart_", 9) || !strncmp(nmz, "w_goc_", 6) || !strncmp(nmz, "w_gic_", 6)) {
      if (!strncmp(nmz, pm, strlen(pm))) nm++; else if (!strncmp(nmz, pg, strlen(pg))) ng++; else if (!strncmp(nmz, pi, strlen(pi))) ni++; else foreign++;
      if (audioTrackBus(t) != 2) foreign++;
    }
  }
  snprintf(d, sizeof d, "пакет %s: W_Mstart_%s %d, W_GOC_%s %d, чужих/не в потоке реплик %d", argv[1], code, nm, code, ng, foreign);
  check("pack", nm >= 3 && ng >= 3 && !foreign, d);
  snprintf(d, sizeof d, "W_GIC_%s %d; absence in source %s; Apu-only waiver by Rob 2026-10-09", code, ni, noGicSource ? "yes" : "no");
  check("gicsrc", noGicSource ? apuEntryWaived && ni == 0 : ni > 0, d);
  sndLevelStart(0.f, 0.f, 0.f);
  // mstart
  int said = 0, distinct = 0, rep = 0; char seen[8][32]; char last[32] = "";
  for (int i = 0; i < 24; i++) {
    int ok = sndSay(SND_SAY_MSTART, 1); const char *nmz = sndSayLastName();
    if (ok && !strncmp(nmz, pm, strlen(pm))) {
      said++;
      if (!strcmp(nmz, last)) rep++;
      snprintf(last, sizeof last, "%s", nmz);
      int k; for (k = 0; k < distinct; k++) if (!strcmp(seen[k], nmz)) break;
      if (k == distinct && distinct < 8) snprintf(seen[distinct++], 32, "%s", nmz);
    }
    run(9.f, 0.f, 0.f);   // реплика доиграла, 5 с между репликами прошли
  }
  snprintf(d, sizeof d, "старт миссии: реплика %d из 24, разных %d, подряд одинаковых %d (последняя %s)", said, distinct, rep, last[0] ? last : "-");
  check("mstart", said == 24 && distinct >= 3 && !rep, d);
  // goc
  int exits = 240, lines = 0, wrong = 0; rep = 0; last[0] = 0;
  for (int i = 0; i < exits; i++) {
    const char *g = sndGetOut(1);
    if (!g) wrong++;   // фронт выхода не замечен
    else if (*g) { lines++; if (strncmp(g, pg, strlen(pg))) wrong++; if (!strcmp(g, last)) rep++; snprintf(last, sizeof last, "%s", g); }
    run(6.5f, 0.f, 0.f); sndGetOut(0); run(.2f, 0.f, 0.f);
  }
  snprintf(d, sizeof d, "выход из машины: реплика на %d выходах из %d (%.0f %%; PS2 5 из 11), не водителя или без фронта %d, подряд одинаковых %d",
           lines, exits, 100.f * lines / exits, wrong, rep);
  check("goc", lines >= exits * 35 / 100 && lines <= exits * 65 / 100 && !wrong && !rep, d);
  // Exact Apu exception only, decision by Rob 2026-10-09; other heroes unchanged.
  // gic (облако 05.10): посадка в машину
  int ins = 240, gl = 0, first = sndGetIn(1) != 0; wrong = 0; rep = 0; last[0] = 0;   // первый вызов: уровень начался за рулём — не фронт
  sndGetIn(0); run(6.f, 0.f, 0.f);
  for (int i = 0; i < ins; i++) {
    const char *g = sndGetIn(1);
    if (sndGetIn(1) != NULL) wrong++; // удержание состояния не новая посадка
    if (!g) wrong++;
    else if (*g) { gl++; if (strncmp(g, pi, strlen(pi))) wrong++; if (!strcmp(g, last)) rep++; snprintf(last, sizeof last, "%s", g); }
    run(6.5f, 0.f, 0.f); sndGetIn(0); run(.2f, 0.f, 0.f);
  }
  snprintf(d, sizeof d, "посадка в машину: реплика на %d посадках из %d (%.0f %%; PS2 ~4 из 11), не водителя или без фронта %d, подряд одинаковых %d, старт за рулём %s",
           gl, ins, 100.f * gl / ins, wrong, rep, first ? "дал реплику" : "без реплики");
  if (apuEntryWaived) printf("INFO   Apu entry voice waived: decision by Rob 2026-10-09 (V93), not a PS2 absence claim\n");
  check("gic", (apuEntryWaived ? gl == 0 : gl >= ins * 26 / 100 && gl <= ins * 46 / 100) && !wrong && !rep && !first, d);
  // room
  if (strcmp(room, "-")) {
    sndLevelStart(0.f, 0.f, 0.f); run(3.f, 0.f, 0.f);   // поток атмосферы разгоняется ~1 с (чтение + наплыв)
    char street[32]; snprintf(street, sizeof street, "%s", amb());
    const char *a = sndRoom(room); run(.5f, 499.f, -304.f); run(2.5f, 503.f, -300.f);   // в комнате ходит
    char in[32]; snprintf(in, sizeof in, "%s", amb());
    sndRoom(NULL); run(3.f, 0.f, 0.f);
    char out[32]; snprintf(out, sizeof out, "%s", amb());
    sndRoom("Moes"); run(3.f, 0.f, 0.f);
    char moe[32]; snprintf(moe, sizeof moe, "%s", amb()); sndRoom(NULL); run(.2f, 0.f, 0.f);
    snprintf(d, sizeof d, "улица %s -> %s: %s (sndRoom %s), в комнате после ходьбы %s -> выход: %s; Moes: %s", street, room, in, a, in, out, moe);
    check("room", !strcmp(in, track) && !strcmp(out, street) && !strcmp(moe, street) && strcmp(street, track), d);
  } else printf("INFO   комнат с атмосферой у уровня нет\n");
  printf("RESULT %s\n", fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}
