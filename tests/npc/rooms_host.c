// Правка 171 (Роб 01.10: «нет Лизы в коридоре школы, нет Апу в Kwik-E-Mart — ходил в пустоту»): фоновые персонажи в комнатах
// получают модель, когда Гомер рядом с ними в той же комнате. Игра без экрана (tools/bots/world.c) с настоящим рантаймом миссий
// и viewer/game_msn.c; персонажи и их места — из скриптов уровня (leveli.mfk AddAmbientCharacter), координат руками нет.
//   room — каждый фоновый, стоящий в комнате (y < −10: комнаты под городом), при Гомере в 1.5 м и Гомере «в комнате»
//          (GameMsn.interior задан, как ставит main.c mvSetInterior) — среди моделей (gameMsnAmbWant, NMODEL_AMB слотов)
//   city — на спавне уровня (город) ни один персонаж комнаты моделей не занимает
// Красный (tests/npc/rooms.sh): -DGAME_AMB_TAG_ONLY — прежний отбор по имени интерьера (правка 140)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
#ifndef SLOTS
#define SLOTS 5   // как NMODEL_AMB вида (viewer/msn_view.c)
#endif
static int fails;
static void check(const char *name, int ok, const char *d) { printf("CHECK %-5s %s  %s\n", name, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "rooms_host LEVEL.shr HOMER.shr level01.msn\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  bwNew(&W); for (int f = 0; f < 60; f++) bwStep(&W, 0, 0, 0);
  GameMsn *M = &W.msn; char d[300]; int nroom = 0;
  for (int i = 0; i < M->nnpc; i++) {
    const GameNpc *c = &M->npc[i];
    if (c->kind == MSN_NPC_MISSION || c->pos.y > -10.f) continue;
    nroom++; M->interior = "room";
    int want[SLOTS], nw = gameMsnAmbWant(M, c->pos.x + 1.5f, c->pos.y, c->pos.z, SLOTS, want), got = 0;
    for (int j = 0; j < nw; j++) if (want[j] == i) got = 1;
    snprintf(d, sizeof d, "%s в комнате (%.1f, %.1f, %.1f), Гомер рядом: моделей %d%s", c->name, c->pos.x, c->pos.y, c->pos.z, nw, got ? "" : " — его НЕТ");
    check("room", got, d);
  }
  check("room", nroom >= 2, nroom >= 2 ? "персонажей в комнатах не меньше 2 (Апу, Лиза)" : "персонажей в комнатах меньше 2 — данные?");
  { const Homer *H = &W.homer; M->interior = 0; int want[SLOTS], nw = gameMsnAmbWant(M, H->x, H->y, H->z, SLOTS, want), bad = 0;
    for (int j = 0; j < nw; j++) if (M->npc[want[j]].pos.y < -10.f) bad = 1;
    snprintf(d, sizeof d, "спавн (%.0f, %.0f): моделей %d, из комнат %s", H->x, H->z, nw, bad ? "ЕСТЬ" : "нет"); check("city", !bad, d); }
  printf("RESULT %s персонажей в комнатах %d, провалов %d\n", fails ? "FAIL" : "PASS", nroom, fails);
  return fails ? 1 : 0;
}
