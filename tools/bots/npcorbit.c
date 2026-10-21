// №813 (Роб 18.10, L2: «Милхаус обходит Барта и начинает бесконечно ходить по кругу; должен идти дальше по своей траектории и стоять
// на своём месте»): игра без экрана, m0 как NEW GAME. Персонаж миссии идёт по маршруту, точка которого — под стоящим игроком:
//   O1 точка под игроком, за ней ещё точка — обязан пройти дальше и дойти до следующей, не кружа вокруг игрока;
//   O2 последняя точка под игроком — обязан встать рядом и стоять (маршрут окончен), не кружа;
//   O3 проход мимо игрока к точке за ним (№510) — как был: дошёл, не сквозь игрока.
//   P1 прохожий трафика: игрок встаёт на его следующую точку пути — прохожий обязан пройти дальше по пути, не кружа.
// Круг меряется углом персонажа вокруг игрока (сумма поворотов со знаком, пока он ближе 2 м): больше 200° — кружит.
//   npcorbit LEVEL HOMER MSN [ИМЯ] -> строки "O ..."/"P ..." и итог "RESULT OK|FAIL" (tests/missions/npc_orbit.sh)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "traffic.h"

static BotWorld W;
static float net, lastA; static int haveA;
static void trackAt(float x, float z) {   // угол вокруг игрока со знаком, пока ближе 2 м
  float dx = x - W.homer.x, dz = z - W.homer.z;
  if (dx * dx + dz * dz > 4.f) { haveA = 0; return; }
  float a = atan2f(dx, dz);
  if (haveA) { float d = a - lastA; while (d > 3.14159265f) d -= 6.2831853f; while (d < -3.14159265f) d += 6.2831853f; net += d; }
  lastA = a; haveA = 1;
}
static int groundAt(float x, float y, float z) { float gy; return colGround(bwCol(), x, z, y + 1.f, y - 1.f, &gy, 0); }
static void npcReset(GameNpc *n, MsnVec3 p0) {
  n->pos = p0; n->walking = 0; n->nwp = 0; n->iwp = 0; n->blocked = 0; n->avoidSide = 0; n->avoidT = 0.f; n->homing = 0;
#ifndef ORBIT_HARNESS_OLD
  n->avoidGive = 0; n->avoidStall = 0.f;
#endif
}
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "npcorbit: нет данных\n"); return 2; }
  bwNew(&W);
  if (!W.haveMsn || !W.haveHomer) { fprintf(stderr, "npcorbit: нет миссий/игрока\n"); return 2; }
  for (int i = 0; i < W.msn.nnpc; i++) { const GameNpc *o = &W.msn.npc[i]; printf("# персонаж %s at %.1f,%.1f,%.1f маршрут %d\n", o->name, o->pos.x, o->pos.y, o->pos.z, o->nwp); }
  GameNpc *n = argc > 4 ? (GameNpc *)gameMsnNpc(&W.msn, argv[4]) : 0;
  if (!n) for (int i = 0; i < W.msn.nnpc && !n; i++) if (W.msn.npc[i].bonus == 0 && !W.msn.npc[i].knock) n = &W.msn.npc[i];
  if (!n) { fprintf(stderr, "npcorbit: нет персонажа\n"); return 2; }
  printf("# %s pos=%.1f,%.1f,%.1f walking=%d iwp=%d nwp=%d home=%.1f,%.1f bonus=%d\n", n->name, n->pos.x, n->pos.y, n->pos.z, n->walking, n->iwp, n->nwp, n->home.x, n->home.z, n->bonus);
  for (int k = 0; k < n->nwp; k++) printf("#   wp%d %.1f,%.1f,%.1f\n", k, n->wp[k].x, n->wp[k].y, n->wp[k].z);
  if (getenv("ORBIT_REAL")) {   // №831: настоящее поведение — игрок стоит на пути персонажа (без подмены маршрута), 40 с; круг и где персонаж
    float tx = n->nwp ? n->wp[n->iwp < n->nwp ? n->iwp : 0].x : n->pos.x + 2.f, tz = n->nwp ? n->wp[n->iwp < n->nwp ? n->iwp : 0].z : n->pos.z;
    float dx = tx - n->pos.x, dz = tz - n->pos.z, dl = hypotf(dx, dz); if (dl < 1e-3f) { dx = 1.f; dz = 0.f; dl = 1.f; }
    float k_ = atof(getenv("ORBIT_REAL")); homerPlace(&W.homer, bwCol(), n->pos.x + dx / dl * k_, n->pos.y + .5f, n->pos.z + dz / dl * k_, 0.f);
    net = 0.f; haveA = 0; float dmin = 1e9f;
    for (int f = 0; f < 60 * 40; f++) { bwStep(&W, 0, 0, 0); trackAt(n->pos.x, n->pos.z); float d = hypotf(W.homer.x - n->pos.x, W.homer.z - n->pos.z); if (d < dmin) dmin = d;
      if (f % 120 == 0) printf("R t=%2d npc=%.1f,%.1f d=%.2f walking=%d iwp=%d blocked=%d avoidT=%.1f give=%d homing=%d h=%.2f круг=%.0f\n", f / 60, n->pos.x, n->pos.z, d, n->walking, n->iwp, n->blocked, n->avoidT, n->avoidGive, n->homing, n->h, fabsf(net) * 57.3f); }
    printf("RESULT REAL круг %.0f° минимум до игрока %.2f\n", fabsf(net) * 57.3f, dmin); return 0; }
  MsnVec3 p0 = n->pos; float dir[2] = {0.f, 0.f};
  for (int k = 0; k < 8; k++) { float a = k * .7853982f, sx = sinf(a), sz = cosf(a); int ok = 1;   // направление, где есть пол на 6 м
    for (float r = 1.f; r <= 6.f && ok; r += 1.f) ok = groundAt(p0.x + sx * r, p0.y, p0.z + sz * r);
    if (ok) { dir[0] = sx; dir[1] = sz; break; } }
  if (dir[0] == 0.f && dir[1] == 0.f) { fprintf(stderr, "npcorbit: нет пола вокруг %s\n", n->name); return 2; }
  printf("# персонаж %s, направление %.2f,%.2f\n", n->name, dir[0], dir[1]);
  const float need = GAME_NPC_RADIUS + HOMER_RADIUS - .05f;
  int bad = 0;
  for (int c = 1; c <= 3; c++) {
    npcReset(n, p0);
    homerPlace(&W.homer, bwCol(), p0.x + dir[0] * 2.f, p0.y + .5f, p0.z + dir[1] * 2.f, 0.f);
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    MsnVec3 H = {W.homer.x, n->pos.y, W.homer.z}, F = {p0.x + dir[0] * 5.f, p0.y, p0.z + dir[1] * 5.f}, B = {p0.x + dir[0] * 4.f, p0.y, p0.z + dir[1] * 4.f};
    if (c == 1) { n->wp[0] = H; n->wp[1] = F; n->nwp = 2; }
    else if (c == 2) { n->wp[0] = H; n->nwp = 1; }
    else { n->wp[0] = B; n->nwp = 1; }
    n->iwp = 0; n->walking = 1; net = 0.f; haveA = 0;
    float dmin = 1e9f, tEnd = -1.f; int F_ = 60 * 14;
    for (int f = 0; f < F_; f++) {
      bwStep(&W, 0, 0, 0); trackAt(n->pos.x, n->pos.z);
      float d = hypotf(W.homer.x - n->pos.x, W.homer.z - n->pos.z); if (d < dmin) dmin = d;
      if (!n->walking && tEnd < 0.f) tEnd = f / 60.f;
    }
    float deg = fabsf(net) * 57.29578f; int fail;
    // №831 (Роб: «обычное поведение NPC», не кружить вокруг игрока): игрок на пути — персонаж стоит и ждёт, у своей точки через 2 с точка пройдена;
    // мера — нет круга (меньше 90°), не сквозь игрока; O2 — встал за 4 с
    if (c == 1) { float dF = hypotf(n->pos.x - F.x, n->pos.z - F.z); fail = deg > 90.f || dmin < need;
      printf("O1 точка под игроком, за ней ещё точка: конец маршрута %s (%.1f с), до следующей точки %.2f м, круг %.0f°, минимум до игрока %.2f, стоит %d -> %s\n",
             tEnd < 0.f ? "нет" : "да", tEnd, dF, deg, dmin, n->blocked, fail ? "FAIL" : "ok"); }
    else if (c == 2) { fail = tEnd < 0.f || tEnd > 4.f || deg > 90.f || dmin < need;
      printf("O2 последняя точка под игроком: встал %s (%.1f с), круг %.0f°, минимум до игрока %.2f -> %s\n", tEnd < 0.f ? "НЕТ" : "да", tEnd, deg, dmin, fail ? "FAIL" : "ok"); }
    else { float dB = hypotf(n->pos.x - B.x, n->pos.z - B.z); fail = dmin < need || deg > 90.f;
      printf("O3 игрок на пути к точке за ним: дошёл %s, до точки %.2f м, круг %.0f°, минимум до игрока %.2f, стоит %d -> %s\n",
             tEnd < 0.f ? "нет (ждёт)" : "да", dB, deg, dmin, n->blocked, fail ? "FAIL" : "ok"); }
    bad += fail;
  }
  npcReset(n, p0);
#ifndef ORBIT_HARNESS_OLD
  n->pcWaitT = 0.f;
#endif
  // P1: прохожий трафика — игрок на его следующей точке пути
  Traffic *t = (Traffic *)bwTraffic();
  if (!W.haveTraffic || !t) printf("P1 прохожий: трафика нет -> пропуск\n");
  else {
    int done = 0;
    for (int tries = 0; tries < 40 && !done; tries++) {
      for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
      for (int j = 0; j < t->maxPeds && !done; j++) {
        TrPed *e = &t->ped[j]; if (e->mode != TRP_WALK || e->test) continue;
        const TrPath *P = &t->path[e->path]; int pn = (int)P->n, k = e->dir > 0 ? e->seg + 1 : e->seg;
        const float *pt = t->pathPt + 3 * (P->first + (uint32_t)((k % pn + pn) % pn));
        float d0 = hypotf(pt[0] - e->x, pt[2] - e->z); if (d0 < 3.f || d0 > 8.f) continue;
        homerPlace(&W.homer, bwCol(), pt[0], pt[1] + .5f, pt[2], 0.f);
        if (hypotf(W.homer.x - pt[0], W.homer.z - pt[2]) > .2f) continue;
        int seg0 = e->seg, dir0 = e->dir, passed = 0, turned = 0; net = 0.f; haveA = 0; float dmin = 1e9f;
        for (int f = 0; f < 60 * 12; f++) {
          bwStep(&W, 0, 0, 0);
          if (e->mode == TRP_OFF) break;
          trackAt(e->x, e->z); float d = hypotf(W.homer.x - e->x, W.homer.z - e->z); if (d < dmin) dmin = d;
          if (e->dir != dir0) turned = 1; else if (e->seg != seg0) passed = 1;
        }
        float deg = fabsf(net) * 57.29578f; int fail = deg > 200.f || (!passed && !turned);
        printf("P1 прохожий %d: игрок на его точке пути (%.1f м впереди): прошёл дальше %s, развернулся %s, круг %.0f°, минимум до игрока %.2f -> %s\n",
               j, d0, passed ? "да" : "нет", turned ? "да" : "нет", deg, dmin, fail ? "FAIL" : "ok");
        bad += fail; done = 1;
      }
    }
    if (!done) printf("P1 прохожий: не нашёлся идущий прохожий -> пропуск\n");
  }
  printf("RESULT %s\n", bad ? "FAIL" : "OK");
  return bad ? 1 : 0;
}
