// Механики уровней 2–7 на настоящем коде игры (tools/bots/world.c + viewer/), без экрана. Гейт tests/levelmech/*.sh.
//   lvmech LEVEL HOMER --barriers [SHIFT]   L2/L5: барьеры 0x3F0000F уровня (типы SPR1 с огнями SP_BILL_PVIS):
//        огни мигают (у каждого огня за 3 с игры >= 2 смены «горит/не горит»), машина на газу от 12 м в центр барьера
//        ломает его (состояние обломка, запущен обломок SP_OP_BREAK, объект ушёл из мира) и не останавливается о него.
//        SHIFT (м) — цель сдвинута вбок: подложенный неверный локатор, барьер не должен сломаться (красный)
//   lvmech LEVEL HOMER --actors             L7: экземпляры SPR1 пакета collect без записей CLT1 (летающие актёры): после 2 с
//        игры строка на экземпляр "A\tиндекс\tx y z\tсостояние\tжив\tколлизия\tбилбордов видно\tнаибольший размер билборда"
// Строки "RESULT: PASS|FAIL" в конце; код выхода 0/1.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static float groundAt(float x, float z, float y0) {
  float y, n[3];
  return colGround(bwCol(), x, z, y0 + 3.f, y0 - 6.f, &y, n) ? y : -1e9f;
}
static int billOn(const StateProps *sp, unsigned i, unsigned b, float ex, float ey, float ez, float *size) {
  float v[12]; uint32_t col, fl; int tex;
  if (!spBillQuad(sp, i, b, ex, ey, ez, v, &col, &tex, &fl) || !(col >> 24)) return 0;
  const SpType *T = &sp->type[sp->inst[i].type]; const SpBill *B = &sp->bill[T->firstBill + b];
  if (size) *size = fmaxf(B->w, B->h);
  return 1;
}
static int isBarrier(const StateProps *sp, unsigned i) {
  const SpType *T = &sp->type[sp->inst[i].type];
  for (unsigned b = 0; b < T->nBill; b++) if (sp->bill[T->firstBill + b].flags & SP_BILL_PVIS) return 1;
  return 0;
}

static int barriers(BotWorld *w, float shift) {
  StateProps *sp = &w->sp; int fails = 0, nb = 0, blinkOk = 0, broke = 0, tried = 0;
  if (!w->haveSP) { printf("нет SPR1 уровня\n"); return 1; }
  // 1) огни: 3 с игры (без машины рядом), смены видимости каждого огня
  unsigned list[64]; int n = 0;
  for (unsigned i = 0; i < sp->ninst && n < 64; i++) if (isBarrier(sp, i)) list[n++] = i;
  nb = n;
  if (!n) { printf("барьеров 0x3F0000F в SPR1 нет\n"); printf("RESULT: FAIL\n"); return 1; }
  static int prev[64][8], flips[64][8];
  memset(prev, -1, sizeof prev); memset(flips, 0, sizeof flips);
  for (int f = 0; f < 180; f++) {
    spUpdate(sp, bwCol(), NULL, NULL, BW_DT);
    for (int k = 0; k < n; k++) {
      unsigned i = list[k]; const SpType *T = &sp->type[sp->inst[i].type]; spPose(sp, i);
      for (unsigned b = 0, l = 0; b < T->nBill && l < 8; b++) {
        if (!(sp->bill[T->firstBill + b].flags & SP_BILL_PVIS)) continue;
        int on = billOn(sp, i, b, sp->run[i].x + 30.f, sp->run[i].y + 5.f, sp->run[i].z + 30.f, NULL);
        if (prev[k][l] >= 0 && on != prev[k][l]) flips[k][l]++;
        prev[k][l] = on; l++;
      }
    }
  }
  for (int k = 0; k < n; k++) {
    const SpType *T = &sp->type[sp->inst[list[k]].type]; int lights = 0, ok = 1;
    for (unsigned b = 0; b < T->nBill && lights < 8; b++) if (sp->bill[T->firstBill + b].flags & SP_BILL_PVIS) { if (flips[k][lights] < 2) ok = 0; lights++; }
    blinkOk += ok;
    if (k < 3 || !ok) printf("B\t%u\tогней %d\tсмен %d %d %d %d\t%s\n", list[k], lights, flips[k][0], flips[k][1], flips[k][2], flips[k][3], ok ? "мигает" : "НЕ мигает");
  }
  printf("огни: мигают у %d из %d барьеров\n", blinkOk, nb);
  if (blinkOk != nb) fails++;
  // 2) удар машиной: по одному барьеру каждого типа, 4 направления подъезда — первое, где машина доезжает
  int doneType[256] = {0};
  for (int k = 0; k < n; k++) {
    unsigned i = list[k], t = sp->inst[i].type;
    if (t < 256 && doneType[t]) continue;
    float c[3], r; spBounds(sp, i, c, &r);
    const float *R = sp->run[i].R; float a0 = atan2f(R[6], R[8]);   // сначала поперёк барьера (вдоль его оси +Z), потом остальные
    int ok = 0;
    for (int d = 0; d < 8 && !ok; d++) {
      bwNew(w); sp = &w->sp;
      static const float off[8] = {0.f, 3.14159265f, 1.57079633f, -1.57079633f, .785398f, -.785398f, 2.35619449f, -2.35619449f};
      float a = a0 + off[d], sx = c[0] - sinf(a) * 12.f, sz = c[2] - cosf(a) * 12.f, sy = groundAt(sx, sz, c[1]);
      if (sy < -1e8f) continue;
      float tx = c[0] + cosf(a) * shift, tz = c[2] - sinf(a) * shift;   // сдвиг вбок, поперёк подъезда
      float h = atan2f(tx - sx, tz - sz);
      bwPlace(w, sx, sy + .3f, sz, h);
      int b0 = sp->breaks; tried++;
      float vmax = 0.f, vafter = -1.f;
      for (int f = 0; f < 240; f++) {
        bwStep(w, GP_CROSS, 0.f, 0.f);
        float v = hypotf(w->car.vel[0], w->car.vel[2]); vmax = fmaxf(vmax, v);
        if (sp->breaks > b0 && vafter < 0.f) vafter = v;
        if (sp->breaks > b0 && !sp->run[i].alive) { ok = 1; break; }
      }
      printf("H\t%u\tтип %u\tнаправление %d\tсдвиг %.1f\tскорость до %.1f м/с\tпосле удара %.1f\t%s\tстарт %.2f %.2f %.4f\tбарьер %.2f %.2f %.2f\n",
             i, t, d, shift, vmax, vafter, ok ? "сломан (обломок, ушёл из мира)" : "цел", sx, sz, h, c[0], c[1], c[2]);
      if (ok && vafter < 1.f) { printf("  машина встала о барьер\n"); ok = 0; }
    }
    if (t < 256) doneType[t] = 1;
    broke += ok;
    if (!ok) fails++;
  }
  printf("удар: сломано %d типов барьеров из %d (попыток %d)\n", broke, broke + (fails - (blinkOk != nb)), tried);
  printf("RESULT: %s\n", fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}

static int actors(BotWorld *w) {
  if (!w->haveColl || !w->coll.haveSp) { printf("нет пакета collect\nRESULT: FAIL\n"); return 1; }
  const Collect *c = &w->coll; StateProps *sp = &w->coll.sp;
  for (int f = 0; f < 120; f++) bwStep(w, 0, 0.f, 0.f);
  int n = 0;
  for (unsigned i = 0; i < sp->ninst; i++) {
    int used = 0;
    for (unsigned k = 0; k < c->ncard; k++) used |= c->card[k].inst == i;
    for (unsigned k = 0; k < c->nwasp; k++) used |= c->wasp[k].inst == i || ((c->wasp[k].flags & COLL_WASP_SHIELD) && c->wasp[k].shield == i);
    for (unsigned k = 0; k < c->ngag; k++) used |= c->gag[k].inst == (int)i;
    if (used) continue;
    const SpRun *r = &sp->run[i]; const SpType *T = &sp->type[sp->inst[i].type];
    int vis = 0; float big = 0.f;
    spPose(sp, i);
    for (unsigned b = 0; b < T->nBill; b++) { float s = 0.f; if (billOn(sp, i, b, r->x + 40.f, r->y - 15.f, r->z + 40.f, &s)) { vis++; big = fmaxf(big, s); } }
    int pieces = 0; for (unsigned k = 0; k < T->nPiece; k++) pieces += spPieceOn(sp, i, k);
    printf("A\t%u\t%.2f %.2f %.2f\t%d\t%d\t%d\t%d\t%.2f\t%d\n", i, r->x, r->y, r->z, r->state, r->alive, r->colOn, vis, big, pieces);
    n++;
  }
  printf("летающих актёров (экземпляров без записей CLT1): %d\nRESULT: %s\n", n, n ? "PASS" : "FAIL");
  return n ? 0 : 1;
}

// --safezone MSN [SHIFT]: каждый этап пакета миссий с AddSafeZone (данные) — вход в этап (msn_resume, как загрузка с
// чекпоинта), игрок в машине в r−3 м от локатора зоны: шкала Hit & Run 0.9 -> 0 за кадр; в r+5 м — остаётся 0.9;
// этап без зоны — зон 0. SHIFT (м) — игрок поставлен со сдвигом: подложенный неверный локатор (красный)
static int safezone(BotWorld *w, float shift) {
  if (!w->haveMsn) { printf("нет пакета миссий\nRESULT: FAIL\n"); return 1; }
  const MsnFile *f = &w->msn.f; int fails = 0, zones = 0;
  for (unsigned mi = 0; mi < f->nmissions; mi++) {
    const MsnMission *M = &f->missions[mi];
    for (int ph = 0; ph < 2; ph++) {
      unsigned pi = ph ? M->main : M->intro; if (pi == MSN_NONE16 || pi >= f->nphases) continue;
      const MsnPhase *P = &f->phases[pi];
      for (unsigned s = 0; s < P->stage_count; s++) {
        const MsnStage *S = &f->stages[P->first_stage + s]; const MsnCmd *z = 0;
        for (unsigned k = 0; k < S->cmd_count && !z; k++) if (f->cmds[S->cmd_first + k].op == MSN_OP_ADDSAFEZONE) z = &f->cmds[S->cmd_first + k];
        int prevZone = 0;   // этап сразу после этапа с зоной: зона прошлого этапа должна уйти
        if (s > 0) { const MsnStage *Q = &f->stages[P->first_stage + s - 1];
          for (unsigned k = 0; k < Q->cmd_count; k++) prevZone |= f->cmds[Q->cmd_first + k].op == MSN_OP_ADDSAFEZONE; }
        if (!z && !prevZone) continue;
        bwNew(w);
        MsnProgress p; memset(&p, 0, sizeof p); p.level = (uint8_t)f->hdr->level; p.story = (uint8_t)mi; p.phase = (uint8_t)ph; p.stage = (uint8_t)s;
        msn_resume(&w->msn.rt, &p);
        for (int fr = 0; fr < 2; fr++) bwStep(w, 0, 0.f, 0.f);
        if (!z) { printf("S\t%s\t%d.%u\tзоны нет в данных\tзон в игре %d\t%s\n", msn_str(f, M->id), ph, s, w->msn.nsafe, w->msn.nsafe ? "FAIL" : "ok");
                  fails += w->msn.nsafe != 0; continue; }
        const MsnLoc *l = msn_arg_loc(f, z, 0); float r = (float)msn_arg_i(f, z, 1); zones++;
        if (!l) { printf("S\t%s\t%d.%u\tлокатор %s не найден\tFAIL\n", msn_str(f, M->id), ph, s, msn_arg_s(f, z, 0)); fails++; continue; }
        float heat[2];
        for (int out = 0; out < 2; out++) {
          float d = out ? r + 5.f : r - 3.f, x = l->pos[0] + d + shift, zz = l->pos[2], y = groundAt(x, zz, l->pos[1]);
          if (y < -1e8f) y = l->pos[1];
          bwPlace(w, x, y + .3f, zz, 0.f);
          w->hnrHeat = .9f; w->hnrCalm = 0.f;
          bwStep(w, 0, 0.f, 0.f);
          heat[out] = w->hnrHeat;
        }
        int ok = w->msn.nsafe >= 1 && heat[0] < 1e-3f && heat[1] > .85f;
        printf("S\t%s\t%d.%u\t%s r=%.0f\tзон в игре %d\tшкала в зоне %.2f, вне %.2f\t%s\n", msn_str(f, M->id), ph, s, msn_arg_s(f, z, 0), r,
               w->msn.nsafe, heat[0], heat[1], ok ? "ok" : "FAIL");
        fails += !ok;
      }
    }
  }
  printf("этапов с AddSafeZone: %d\nRESULT: %s\n", zones, fails || (!zones && f->hdr->level == 2) ? "FAIL" : "PASS");
  return fails || (!zones && f->hdr->level == 2) ? 1 : 0;
}

// --shield: щиты ос (AddShield) пакета collect: у каждой осы со щитом — появление рядом с игроком, щит на осе, удары пинком
// Гомера (событие HIT в точке осы): все, кроме последнего из COLL_SHIELD_HP, — щит держит (s2), следующий — пролом (s3), оса жива;
// следующий удар — оса DESTROYED; через 1 с щит гаснет. Строка "W\tоса\tщит\tудары..." на осу; осы без щита — удар сразу убивает
static int shieldTest(BotWorld *w, int limit) {
  if (!w->haveColl || !w->coll.haveSp) { printf("нет пакета collect\nRESULT: FAIL\n"); return 1; }
  Collect *c = &w->coll; int fails = 0, tested = 0, shielded = 0;
  for (unsigned i = 0; i < c->nwasp; i++) shielded += (c->wasp[i].flags & COLL_WASP_SHIELD) != 0;
  printf("ос %u, со щитом %d\n", c->nwasp, shielded);
  for (unsigned i = 0; i < c->nwasp && tested < limit; i++) {
    bwNew(w);
    const CollWasp *W = &c->wasp[i]; float y, n[3];
    float gy = colGround(bwCol(), W->x, W->z + 3.f, W->y + 2.f, W->y - 40.f, &y, n) ? y : W->y - 2.f;
    bwPlace(w, W->x, gy + .3f, W->z + 3.f, 0.f);
    for (int f = 0; f < 90 && c->st.waspSt[i] != 1; f++) bwStep(w, 0, 0.f, 0.f);
    if (c->st.waspSt[i] != 1) { printf("W\t%s\tне появилась\n", W->name); continue; }
    for (int f = 0; f < 60; f++) bwStep(w, 0, 0.f, 0.f);   // появление (s0 1.25 с у осы, 0.67 с у щита)
    tested++;
    char log[160]; int n0 = 0, ok = 1, killedAt = -1;
    int hasShield = (W->flags & COLL_WASP_SHIELD) != 0;
    for (int h = 0; h < 4 && killedAt < 0; h++) {
      SpRun *r = &c->sp.run[W->inst];
      HomerEvent e = {HOMER_EV_HIT, r->x, r->y, r->z, .6f, 0.f, 1.f};
      collectHomerHit(c, &e);
      for (int f = 0; f < 2; f++) bwStep(w, 0, 0.f, 0.f);
      int ss = hasShield ? c->sp.run[W->shield].state : -1, dead = c->st.waspSt[i] == 2 || c->sp.run[W->inst].state == 5;
      n0 += snprintf(log + n0, sizeof log - n0, " %d:щит=%d%s", h + 1, ss, dead ? ",оса убита" : "");
      if (dead) killedAt = h + 1;
      for (int f = 0; f < 30; f++) bwStep(w, 0, 0.f, 0.f);
    }
    for (int f = 0; f < 90; f++) bwStep(w, 0, 0.f, 0.f);
    int gone = !hasShield || !c->sp.run[W->shield].alive;
    int want = hasShield ? 3 : 1;   // COLL_SHIELD_HP ударов щиту + один осе
    ok = killedAt == want && gone;
    printf("W\t%s\tщит %s\tудары:%s\tубита на %d-м (ждали %d)\tщит погас %s\t%s\n", W->name, hasShield ? "да" : "нет", log, killedAt, want,
           gone ? "да" : "нет", ok ? "ok" : "FAIL");
    fails += !ok;
  }
  // удар машиной: первая оса со щитом, машина в 10 м на газу в неё — щит принимает удар, оса жива
  int carOk = !shielded;
  for (unsigned i = 0; i < c->nwasp && !carOk; i++) {
    const CollWasp *W = &c->wasp[i]; if (!(W->flags & COLL_WASP_SHIELD)) continue;
    bwNew(w); float y, n[3];
    float gy = colGround(bwCol(), W->x, W->z + 3.f, W->y + 2.f, W->y - 40.f, &y, n) ? y : W->y - 2.f;
    bwPlace(w, W->x, gy + .3f, W->z + 3.f, 0.f);
    for (int f = 0; f < 150; f++) bwStep(w, 0, 0.f, 0.f);
    if (c->st.waspSt[i] != 1) continue;
    SpRun *r = &c->sp.run[W->inst];
    for (int k = 0; k < 4 && !carOk; k++) {   // четыре стороны подъезда
      float a = k * 1.5707963f, sx = r->x - sinf(a) * 10.f, sz = r->z - cosf(a) * 10.f;
      float sy = colGround(bwCol(), sx, sz, r->y + 3.f, r->y - 40.f, &y, n) ? y : gy;
      unsigned h0 = c->st.shieldHits;
      bwPlace(w, sx, sy + .3f, sz, atan2f(r->x - sx, r->z - sz));
      for (int f = 0; f < 120 && c->st.shieldHits == h0; f++) bwStep(w, GP_CROSS, 0.f, 0.f);
      int alive = c->st.waspSt[i] == 1 && r->state != 5;
      printf("C\t%s\tподъезд %d\tударов по щиту %u\tоса %s\n", W->name, k, c->st.shieldHits - h0, alive ? "жива" : "убита");
      carOk = c->st.shieldHits > h0 && alive;
    }
  }
  if (!carOk) { printf("удар машиной по щиту не прошёл\n"); fails++; }
  printf("осы проверены: %d; удары по щитам %u, проломы %u\n", tested, c->st.shieldHits, c->st.shieldBreaks);
  int bad = fails || !tested;
  printf("RESULT: %s\n", bad ? "FAIL" : "PASS");
  return bad;
}

// --wide [SHIFT]: стейтпропы уровня шире 32 слотов (обезьяны l2/l5_monkiesgag 47 слотов): машина на газу от 12 м в центр —
// событие удара переводит в s1 данных (все части видны, в т. ч. слоты 32+), объём снят, через 6 с (вызов REMOVE_FROM_WORLD)
// объект ушёл из мира. SHIFT — цель сдвинута вбок (неверный локатор, красный). Строка "M\t..." на тип
static int wide(BotWorld *w, float shift) {
  StateProps *sp = &w->sp; int fails = 0, n = 0;
  for (unsigned i = 0; i < sp->ninst; i++) {
    const SpType *T = &sp->type[sp->inst[i].type];
    if (T->visWords <= 1 || T->kind) continue;
    n++;
    unsigned slots = spSlotCount(sp, sp->inst[i].type), on0 = 0;
    for (unsigned k = 0; k < slots; k++) on0 += spSlotOn(sp, i, k);
    float c[3], r; spBounds(sp, i, c, &r);
    int ok = 0; unsigned on1 = 0, hi1 = 0; float gone = -1.f;
    for (int d = 0; d < 8 && !ok; d++) {
      bwNew(w); sp = &w->sp;
      float a = d * 0.785398f, sx = c[0] - sinf(a) * 12.f, sz = c[2] - cosf(a) * 12.f, sy = groundAt(sx, sz, c[1]);
      if (sy < -1e8f) continue;
      float tx = c[0] + cosf(a) * shift, tz = c[2] - sinf(a) * shift;
      bwPlace(w, sx, sy + .3f, sz, atan2f(tx - sx, tz - sz));
      int f = 0;
      for (; f < 240 && sp->run[i].state == 0; f++) bwStep(w, GP_CROSS, 0.f, 0.f);
      if (sp->run[i].state != 1) continue;
      on1 = hi1 = 0;
      for (unsigned k = 0; k < slots; k++) { int o = spSlotOn(sp, i, k); on1 += o; if (k >= 32) hi1 += o; }
      for (int g = 0; g < 480 && sp->run[i].alive; g++) bwStep(w, 0, 0.f, 0.f);
      gone = sp->run[i].alive ? -1.f : sp->run[i].t;
      ok = on1 > on0 && hi1 > 0 && !sp->run[i].colOn && !sp->run[i].alive;
    }
    printf("M\t%u\tслотов %u\tвидно до удара %u, после %u (из них 32+: %u)\tушёл из мира %s\t%s\n", i, slots, on0, on1, hi1,
           gone >= 0.f ? "да" : "нет", ok ? "ok" : "FAIL");
    fails += !ok;
  }
  printf("стейтпропов шире 32 слотов: %d\nRESULT: %s\n", n, fails || !n ? "FAIL" : "PASS");
  return fails || !n;
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: lvmech LEVEL HOMER --barriers [SHIFT] | --actors | --safezone MSN [SHIFT]\n"); return 2; }
  if (!strcmp(argv[3], "--safezone")) {
    if (argc < 5 || bwData(argv[1], argv[2], argv[4])) { fprintf(stderr, "bwData\n"); return 2; }
    static BotWorld w; if (bwNew(&w)) return 2;
    return safezone(&w, argc > 5 ? (float)atof(argv[5]) : 0.f);
  }
  int e = bwData(argv[1], argv[2], 0);
  if (e) { fprintf(stderr, "bwData %d\n", e); return 2; }
  static BotWorld w; if (bwNew(&w)) { fprintf(stderr, "bwNew\n"); return 2; }
  if (!strcmp(argv[3], "--barriers")) return barriers(&w, argc > 4 ? (float)atof(argv[4]) : 0.f);
  if (!strcmp(argv[3], "--actors")) return actors(&w);
  if (!strcmp(argv[3], "--wide")) return wide(&w, argc > 4 ? (float)atof(argv[4]) : 0.f);
  if (!strcmp(argv[3], "--shield")) return shieldTest(&w, argc > 4 ? atoi(argv[4]) : 4);
  return 2;
}
