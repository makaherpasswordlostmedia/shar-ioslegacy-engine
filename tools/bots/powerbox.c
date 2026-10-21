// Щитки m4 (П1, L1_ФИНИШ 30.09): предметы миссии «сломать» — игра без экрана, тот же код, что EBOOT (viewer/game_msn.c).
// m4 «Blind Big Brother», основная часть (с её чекпоинта): Гомер ставится в сферу старта (m4_start_sd, маркер этапа 0) — этап
// delivery включает 9 щитков PP_powerbox1..9 (стейтпропы с тегом, s0 -> s1). Потом Гомер у щитка с тегом 3 бьёт □ дважды
// (данные диска: s1 HIT -> s2, s2 HIT -> s3 OBJECT_DESTROYED) — цель засчитана (1 из 9), щиток 3 сломан, остальные целы.
//   powerbox LEVEL HOMER MSN   -> строки "P ..." и итог "RESULT OK|FAIL" (tests/missions/powerbox.sh)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static BotWorld W;
static int tagState(int tag, int *inst) {   // состояние стейтпропа с тегом (-1 — нет такого)
  for (unsigned i = 0; i < W.sp.ninst; i++) if (W.sp.inst[i].tag == tag) { if (inst) *inst = (int)i; return W.sp.run[i].state; }
  return -1;
}
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "powerbox: нет данных\n"); return 2; }
  bwNew(&W);
  if (!W.haveMsn || !W.haveHomer || !W.haveSP) { fprintf(stderr, "powerbox: нет миссий/Гомера/стейтпропов\n"); return 2; }
  int mi = msn_find_mission(&W.msn.f, "m4"); if (mi < 0) { fprintf(stderr, "powerbox: нет миссии m4\n"); return 2; }
  int tagged = 0; for (unsigned i = 0; i < W.sp.ninst; i++) tagged += W.sp.inst[i].tag != 0;
  printf("P стейтпропов с тегом щитка: %d\n", tagged);
  for (unsigned i = 0; i < W.sp.ninst; i++) if (W.sp.inst[i].tag) {   // где щиток и земля под ним (Гомер достаёт пинком с земли)
    const SpInst *I = &W.sp.inst[i]; float g = -99.f; int ok = colGround(bwCol(), I->x, I->z, I->y + 1.f, I->y - 6.f, &g, 0);
    printf("P щиток %d: %.1f %.1f %.1f, земля %s %.1f\n", I->tag, I->x, I->y, I->z, ok ? "" : "нет", g); }
  MsnRuntime *rt = &W.msn.rt; rt->cp_phase = 1; rt->cp_stage = 0; msn_start_mission(rt, mi, 1);   // основная часть (как missioner --from-main)
  int bad = 0, f;
  for (f = 0; f < 60 * 20 && !(rt->status == MSN_RUNNING && W.msn.markerOn && rt->obj == MSN_OBJ_GOTO); f++) bwStep(&W, 0, 0, 0);
  if (!W.msn.markerOn) { printf("P нет маркера этапа 0 (m4_start_sd)\nRESULT FAIL\n"); return 1; }
  MsnVec3 p = W.msn.marker.pos;
  homerPlace(&W.homer, bwCol(), p.x, p.y + .5f, p.z, 0.f);   // в сферу старта (проверяется включение щитков, не дорога к ним)
  for (f = 0; f < 60 * 20 && rt->obj != MSN_OBJ_DELIVERY; f++) bwStep(&W, 0, 0, 0);
  if (rt->obj != MSN_OBJ_DELIVERY) { printf("P этап delivery не начался\nRESULT FAIL\n"); return 1; }
  for (f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
  int on = 0; for (int t = 1; t <= 9; t++) on += tagState(t, 0) == 1;
  printf("P этап delivery: предметов %d, щитков в s1 %d из 9 -> %s\n", rt->nitems, on, on == 9 ? "ok" : "FAIL"); bad += on != 9;
  int i3 = -1; if (tagState(3, &i3) < 0) { printf("P нет щитка с тегом 3\nRESULT FAIL\n"); return 1; }
  const SpInst *I = &W.sp.inst[i3];
  float c[3], r; spBounds(&W.sp, (unsigned)i3, c, &r);
  float a = 0.f, hx = I->x + sinf(a) * 1.2f, hz = I->z + cosf(a) * 1.2f;   // Гомер в 1.2 м от щитка, лицом к нему
  for (int k = 0; k < 8; k++) {   // сторона, где Гомер встаёт на землю не выше щитка на 1 м (щиток у стены — другая сторона)
    a = k * .7853982f; hx = I->x + sinf(a) * 1.2f; hz = I->z + cosf(a) * 1.2f;
    homerPlace(&W.homer, bwCol(), hx, I->y + .5f, hz, a + 3.14159265f);
    for (f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    if (W.homer.grounded && fabsf(W.homer.y - I->y) < 1.f && hypotf(W.homer.x - I->x, W.homer.z - I->z) < 1.6f) break;
  }
  int n0 = rt->ncollected, s0 = W.sp.run[i3].state;
  for (int k = 0; k < 2; k++) {   // □ — пинок (game.c: hi.attack), дважды с паузой
    float r2 = atan2f(I->x - W.homer.x, I->z - W.homer.z);
    homerPlace(&W.homer, bwCol(), W.homer.x, W.homer.y + .05f, W.homer.z, r2);   // лицом к щитку
    bwStep(&W, GP_SQUARE, 0, 0); for (f = 0; f < 60; f++) bwStep(&W, 0, 0, 0);
    printf("P пинок %d: щиток 3 в s%d\n", k + 1, W.sp.run[i3].state);
  }
  for (f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
  int s1 = W.sp.run[i3].state, got = rt->ncollected - n0, others = 0;
  for (int t = 1; t <= 9; t++) if (t != 3) others += tagState(t, 0) == 1;
  printf("P щиток 3: s%d -> s%d, засчитано целей %d (всего %d из %d), остальные в s1 %d из 8 -> %s\n", s0, s1, got, rt->ncollected, rt->nitems, others,
         s1 == 3 && got == 1 && others == 8 ? "ok" : "FAIL");
  bad += !(s1 == 3 && got == 1 && others == 8);
  printf("RESULT %s\n", bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
