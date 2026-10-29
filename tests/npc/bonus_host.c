// Правка 180 (близнецы 03.10): персонажи бонус-миссий стоят на своих местах с начала уровня, как у оригинала (О4 louie_school:
// кадр f03600 — Ральф гонки sr3 на sr3_ralph_sd под клетчатым флагом, f04600 — Луи у школы под кубиками; Б2 — louie_m, nelson_m,
// cletus_m читаются за ~150 м от их мест). Игра без экрана (tools/bots/world.c) с настоящим рантаймом миссий и viewer/game_msn.c;
// имена и места — из скриптов уровня (AddNPCCharacterBonusMission), координат руками нет.
//   stand — каждый персонаж бонус-миссии уровня стоит на своём локаторе (не дальше 0,5 м) сразу после старта уровня
//   talk  — пешком в 1 м от него: msn_bonus_near — его миссия (△ — разговор и миссия)
//   two   — фоновый с тем же именем (Ральф: AddAmbientCharacter) — отдельный человек на своём месте
//   amb   — у фонового двойника бонус-миссия не начинается (msn_bonus_near = −1)
//   back  — бонус-миссия началась (вступление берёт персонажа себе, двойник на месте) и отменена: персонаж снова на своём месте
// Красный (tests/npc/bonus.sh): -DGAME_BONUS_NPC=0 — прежнее (бонусных в мире нет)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
static int fails;
static void check(const char *name, int ok, const char *d) { printf("CHECK %-5s %s  %s\n", name, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static BotWorld W;
static const GameNpc *bonusNpc(const GameMsn *M, int mi) {
  for (int i = 0; i < M->nnpc; i++) if (M->npc[i].bonus == mi + 1) return &M->npc[i];
  return 0;
}
static const GameNpc *otherNpc(const GameMsn *M, const char *name, int kind) {   // не бонусный с этим именем (kind < 0 — любой)
  for (int i = 0; i < M->nnpc; i++)
    if (!M->npc[i].bonus && msn_streq(M->npc[i].name, name) && (kind < 0 || M->npc[i].kind == kind)) return &M->npc[i];
  return 0;
}
static int nearAt(GameMsn *M, float x, float y, float z) {   // msn_bonus_near пешком в городе в точке
  MsnWorld w; gameMsnWorld(M, &w); w.player.x = x; w.player.y = y; w.player.z = z; w.on_foot = 1; w.interior = 0;
  return msn_bonus_near(&M->rt, &w);
}
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "bonus_host LEVEL.shr HOMER.shr level01.msn\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  bwNew(&W);
  GameMsn *M = &W.msn; const MsnFile *F = &M->f; char d[300]; int ngiver = 0, ntwo = 0, backMi = -1;
  for (uint32_t mi = 0; mi < F->nmissions; mi++) {
    const MsnMission *ms = &F->missions[mi];
    if (!(ms->flags & MSN_MF_BONUS) || ms->bonus_npc == 0xFFFFFFFFu) continue;
    const MsnCmd *c = &F->cmds[ms->bonus_npc]; const char *name = msn_arg_s(F, c, 0); const MsnLoc *L = msn_arg_loc(F, c, 2);
    if (!L) continue;
    ngiver++;
    const GameNpc *n = bonusNpc(M, (int)mi);
    float dist = n ? hypotf(n->pos.x - L->pos[0], n->pos.z - L->pos[2]) : -1.f;
    snprintf(d, sizeof d, "%s (%s): локатор %s (%.1f, %.1f, %.1f) — %s", msn_str(F, ms->id), name, msn_arg_s(F, c, 2), L->pos[0], L->pos[1], L->pos[2],
             n ? "стоит" : "его НЕТ в мире");
    if (n) snprintf(d + strlen(d), sizeof d - strlen(d), " в %.2f м", dist);
    check("stand", n && dist <= .5f, d);
    int b = nearAt(M, L->pos[0] + 1.f, L->pos[1], L->pos[2]);
    snprintf(d, sizeof d, "%s: пешком в 1 м от %s — бонус %s", msn_str(F, ms->id), name, b >= 0 ? msn_str(F, F->missions[b].id) : "нет");
    check("talk", b == (int)mi, d);
    const GameNpc *o = otherNpc(M, name, MSN_NPC_AMBIENT);
    if (o) {
      ntwo++; backMi = (int)mi; float od = hypotf(o->pos.x - L->pos[0], o->pos.z - L->pos[2]);
      snprintf(d, sizeof d, "%s: фоновый двойник в (%.1f, %.1f), от места %s %.0f м", name, o->pos.x, o->pos.z, msn_str(F, ms->id), od);
      check("two", n && o != n && od > 5.f, d);
      int a = nearAt(M, o->pos.x + 1.f, o->pos.y, o->pos.z);
      snprintf(d, sizeof d, "%s: у фонового двойника — бонус %s", name, a >= 0 ? msn_str(F, F->missions[a].id) : "нет");
      check("amb", a < 0, d);
    }
  }
  check("stand", ngiver >= 5, ngiver >= 5 ? "персонажей бонус-миссий уровня не меньше 5" : "персонажей бонус-миссий меньше 5 — данные?");
  check("two", ntwo >= 1, ntwo >= 1 ? "есть фоновый двойник бонусного (Ральф)" : "двойника нет — данные?");
  if (backMi >= 0) {   // вступление бонус-миссии двойника, потом отмена
    const MsnCmd *c = &F->cmds[F->missions[backMi].bonus_npc]; const char *name = msn_arg_s(F, c, 0); const MsnLoc *L = msn_arg_loc(F, c, 2);
    const GameNpc *o0 = otherNpc(M, name, MSN_NPC_AMBIENT); MsnVec3 amb0 = o0 ? o0->pos : (MsnVec3){0, 0, 0};
    int st = msn_start_bonus(&M->rt, backMi);
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    const GameNpc *mn = otherNpc(M, name, MSN_NPC_MISSION), *o1 = otherNpc(M, name, MSN_NPC_AMBIENT);
    float md = mn ? hypotf(mn->pos.x - L->pos[0], mn->pos.z - L->pos[2]) : -1.f, ad = o1 ? hypotf(o1->pos.x - amb0.x, o1->pos.z - amb0.z) : -1.f;
    snprintf(d, sizeof d, "старт %s=%d: %s миссии %s (%.1f м от места), двойник %s (сдвинулся на %.1f м), бонусного %s",
             msn_str(F, F->missions[backMi].id), st, name, mn ? "есть" : "НЕТ", md, o1 ? "на месте" : "ПРОПАЛ", ad, bonusNpc(M, backMi) ? "ДВА" : "нет");
    check("back", st && mn && md <= .5f && o1 && !bonusNpc(M, backMi), d);
    gameMsnAbort(M);
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    const GameNpc *n2 = bonusNpc(M, backMi);
    float d2 = n2 ? hypotf(n2->pos.x - L->pos[0], n2->pos.z - L->pos[2]) : -1.f;
    snprintf(d, sizeof d, "отмена: %s бонус-миссии %s (%.2f м от места), персонажей миссии с этим именем %s", name, n2 ? "снова стоит" : "НЕ вернулся", d2,
             otherNpc(M, name, MSN_NPC_MISSION) ? "ОСТАЛСЯ" : "нет");
    check("back", n2 && d2 <= .5f && !otherNpc(M, name, MSN_NPC_MISSION), d);
  }
  printf("RESULT %s персонажей бонус-миссий %d, двойников %d, провалов %d\n", fails ? "FAIL" : "PASS", ngiver, ntwo, fails);
  return fails ? 1 : 0;
}
