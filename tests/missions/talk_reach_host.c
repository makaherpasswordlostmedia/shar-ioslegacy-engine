// Правка 345 (атлас миссий 332, Роб 05.10: «всё как в оригинале»): дальность разговора △ с персонажем миссии.
// [PS2] своя pcsx2-twins без окна и звука (05.10, agent345/ps2: slowA/slowC/sideD/apu1): Мардж (m0sd, SetTalkToTarget без 4-го
// аргумента) — △ в 1,310 м от неё не открывает разговор, в 1,295 м открывает (подход с другой стороны: 1,304 нет, 1,291 да);
// Апу (m0i, аргумент "3.0") — 3,022 нет, 2,959 да. Правило: 4-й аргумент SetTalkToTarget — радиус, без него 1,3 м, без запаса.
// Игра без экрана (tools/bots/world.c) с настоящим рантаймом миссий и viewer/game_msn.c; персонаж — где стоит в мире.
//   data  — по всем SetTalkToTarget всех уровней (build/missions/level0N.msn): дальность = аргумент 4 или 1,3 м
//   marge — уровень 1, этап m0sd.0: Гомер пешком на d м от Мардж, △: в 1,0 м разговор начинается, в 1,6 и 2,5 м — нет
//   hint  — подсказка △ (gameMsnWantsMissionAction) — по той же границе
// Красный (tests/missions/talk_reach.sh): --old — msnTalkOld = 1 (прежнее: 3 м или аргумент + 1 м запаса) обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static int fails;
static void check(const char *name, int ok, const char *d) { printf("CHECK %-5s %s  %s\n", name, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static BotWorld W; static BotSnap S;

static const GameNpc *npcNamed(const GameMsn *M, const char *name) {
  for (int i = 0; i < M->nnpc; i++) if (msn_streq(M->npc[i].name, name) && M->npc[i].kind == MSN_NPC_MISSION) return &M->npc[i];
  for (int i = 0; i < M->nnpc; i++) if (msn_streq(M->npc[i].name, name)) return &M->npc[i];
  return 0;
}
// Гомер на d м от собеседника этапа (по линии от него к Гомеру), лицом к нему; hint — подсказка △ здесь; вернёт 1, если △ начал разговор
static int talkAt(float d, float *dReal, int *hint) {
  bwLoad(&W, &S);
  GameMsn *M = &W.msn; MsnRuntime *rt = &M->rt;
  const GameNpc *n = npcNamed(M, rt->target); if (!n) return -1;
  float dx = W.homer.x - n->pos.x, dz = W.homer.z - n->pos.z, l = hypotf(dx, dz);
  if (l < .01f) { dx = 1.f; dz = 0.f; l = 1.f; }
  homerPlace(&W.homer, bwCol(), n->pos.x + dx / l * d, n->pos.y + .5f, n->pos.z + dz / l * d, atan2f(-dx, -dz));
  bwStep(&W, 0, 0, 0);                                         // кадр на месте: Гомер на земле, мир увидел новое положение
  n = npcNamed(M, rt->target);
  *dReal = sqrtf((W.homer.x - n->pos.x) * (W.homer.x - n->pos.x) + (W.homer.y - n->pos.y) * (W.homer.y - n->pos.y) +
                 (W.homer.z - n->pos.z) * (W.homer.z - n->pos.z));
  *hint = gameMsnWantsMissionAction(M);
  int st0 = rt->stage, ph0 = rt->phase, obj0 = rt->obj;
  bwStep(&W, GP_TRIANGLE, 0, 0);
  for (int k = 0; k < 20; k++) bwStep(&W, 0, 0, 0);
  return rt->obj != obj0 || rt->stage != st0 || rt->phase != ph0;
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "talk_reach_host LEVEL.shr HOMER.shr MSN_DIR [--old]\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  msnTalkOld = argc > 4 && !strcmp(argv[4], "--old");
  char d[300];
  // data: все уровни
  int nTalk = 0, nArg = 0, badData = 0;
  for (int lv = 1; lv <= 7; lv++) {
    char fn[512]; snprintf(fn, sizeof fn, "%s/level0%d.msn", argv[3], lv);
    FILE *f = fopen(fn, "rb"); if (!f) { snprintf(d, sizeof d, "нет %s", fn); check("data", 0, d); continue; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    void *buf = malloc((size_t)sz); if (!buf || fread(buf, 1, (size_t)sz, f) != (size_t)sz) { fclose(f); free(buf); continue; } fclose(f);
    MsnFile F; char err[128];
    if (msn_open(&F, buf, (size_t)sz, err, sizeof err)) { snprintf(d, sizeof d, "%s: %s", fn, err); check("data", 0, d); free(buf); continue; }
    MsnRuntime rt; memset(&rt, 0, sizeof rt); rt.f = &F; rt.talk_radius = MSN_TALK_R;
    for (uint32_t i = 0; i < F.ncmds; i++) {
      const MsnCmd *c = &F.cmds[i]; if (c->op != MSN_OP_SETTALKTOTARGET) continue;
      nTalk++; int has = msn_argc(c) > 3 && msn_arg_f(&F, c, 3) > 0; nArg += has;
      float want = has ? msn_arg_f(&F, c, 3) : 1.3f, got = msn_talk_reach(&rt, c);
      if (fabsf(got - want) > 1e-4f) { badData++;
        snprintf(d, sizeof d, "уровень %d: SetTalkToTarget(%s%s%s) — дальность %.2f м, по данным %.2f", lv, msn_arg_s(&F, c, 0),
                 has ? ", радиус " : "", has ? msn_arg_s(&F, c, 3) : "", got, want);
        if (badData <= 3) check("data", 0, d); }
    }
    free(buf);
  }
  snprintf(d, sizeof d, "SetTalkToTarget на 7 уровнях: %d (с радиусом в данных %d), не по данным %d", nTalk, nArg, badData);
  check("data", nTalk > 50 && nArg >= 4 && !badData, d);

  // marge: уровень 1, m0sd.0
  char lvl[512]; snprintf(lvl, sizeof lvl, "%s/level01.msn", argv[3]);
  if (bwData(argv[1], argv[2], lvl)) { printf("FAIL: данные мира\n"); return 1; }
  bwNew(&W); bwSaveAlloc(&W, &S);
  GameMsn *M = &W.msn; MsnRuntime *rt = &M->rt;
  for (int k = 0; k < 180; k++) bwStep(&W, 0, 0, 0);            // SetInitialWalk: Гомер дошёл до level1_homer_walkto
  snprintf(d, sizeof d, "этап: миссия %d фаза %d этап %d цель %d собеседник %s", rt->cur, rt->phase, rt->stage, rt->obj, rt->target ? rt->target : "-");
  int ok0 = rt->status == MSN_RUNNING && rt->obj == MSN_OBJ_TALKTO && rt->target && msn_streq(rt->target, "marge") && npcNamed(M, "marge");
  check("stage", ok0, d);
  if (!ok0) { printf("RESULT FAIL\n"); return 1; }
  { const GameNpc *mg = npcNamed(M, "marge");   // справка: где Мардж от Гомера после SetInitialWalk (оригинал: 1,57 м, △ там не работает)
    printf("INFO  старт m0sd: Гомер (%.2f %.2f) — Мардж (%.2f %.2f), %.2f м\n", W.homer.x, W.homer.z, mg->pos.x, mg->pos.z,
           hypotf(W.homer.x - mg->pos.x, W.homer.z - mg->pos.z)); }
  bwSave(&W, &S);
  static const float D[] = {1.0f, 1.6f, 2.5f}; static const int WANT[] = {1, 0, 0};
  for (int i = 0; i < 3; i++) {
    float dr = 0; int hint = 0, t = talkAt(D[i], &dr, &hint);
    snprintf(d, sizeof d, "Мардж: Гомер в %.2f м (задано %.1f), △ — %s; подсказка △ %s (оригинал: в 1,30 м граница)", dr, D[i],
             t > 0 ? "разговор" : t < 0 ? "нет персонажа" : "ничего", hint ? "есть" : "нет");
    check("marge", t == WANT[i], d);
    snprintf(d, sizeof d, "подсказка △ в %.2f м: %s", dr, hint ? "есть" : "нет");
    check("hint", hint == WANT[i], d);
  }
  // граница порта (справка, не судится): шаг 5 см
  float lo = -1, hi = -1;
  for (float x = 0.9f; x <= 2.0f; x += 0.05f) { float dr; int hint, t = talkAt(x, &dr, &hint); if (t > 0) lo = dr; else if (hi < 0) hi = dr; }
  printf("INFO  граница порта: разговор в %.2f м, нет в %.2f м (msnTalkOld=%d)\n", lo, hi, msnTalkOld);
  printf("RESULT %s\n", fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}
