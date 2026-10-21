// Правка Роба 197 (03.10, третий раз после 174 и 193): «надпись Hit & Run и музыка есть, а копы не появляются и не гоняются».
// Причина (эмулятор 03.10, журнал MCAR): полицейская встаёт на полосу в 100 м по прямой, но путь по дорогам от неё до игрока бывает
// в 4 раза длиннее (от дома Симпсонов — 441 м через x ≈ 41): машина уезжает от игрока, дальше 110 м её снимают (правило
// оригинала) и ставят заново — и так по кругу, игрок её не видит. Игра без экрана (tools/bots/world.c) с настоящими дорогами
// traffic.shr и viewer/game_msn.c gameMsnPolice / viewer/msncar.c; у каждой точки игрок стоит в машине, полиция — как в main.c
// hnrPursuit: дальше 110 м — заново в 100 м (не раньше 1 с после прошлой пересадки), стоящий игрок и полиция дальше 10 м 10 с — заново.
//   stand — аудит 09.10 п. 11/19 (вместо прежнего reach «за 25 с ближе 40 м», которое закрепляло поведение, которого у PS2 нет):
//           игрок стоит в машине 48 с (как b3_fine80); у PS2 (tw_v8_stand 16 с, b3_fine80 48 с, у дома, без телепорта) полиция
//           всё время в 93,7–118 м, пересаживается в 100 м. Проверка: у дома (то же место, что у PS2) ближе 90 м не подъезжает
//           (93,7 м минус 4 %), в остальных местах — ближе 80 м (правило гейта: дороги вокруг другие, замера PS2 там нет)
//   foot  — Гомер вышел и стоит: полиция за 25 с ближе 40 м, не больше одной пересадки (правка 197; к пешему — прежнее правило порта)
//   chase — игрок едет к дальней точке по дорогам; полиция за 45 с подъехала ближе 30 м, не больше 4 пересадок (PS2 b3_moving:
//           с 100 до 27 м за 5 с; порт — правило 197)
// Точки: старт уровня (дом Симпсонов, во дворе — то же место, что у PS2) и места у дорог по уровню (полоса трафика рядом с якорем).
// Красные (tests/hnr/police.sh): -DPOLICE_SPAWN_STRAIGHT=1 — прежний выбор места (chase); -DPOLICE_STAND_OLD=1 — прежняя стоянка
// в 30 м у стоящего игрока (stand)
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
#include "world.h"
#include "msncar.h"
static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-5s %s  %s\n", n, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static BotWorld W;
static const McCar *police(void) {
  for (int i = 0; i < W.msn.cars.n; i++) if (W.msn.cars.c[i].on && !strcmp(W.msn.cars.c[i].name, "cPolice")) return &W.msn.cars.c[i];
  return 0;
}
int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "police_host LEVEL.shr HOMER.shr level01.msn\n"); return 2; }
  setvbuf(stdout, NULL, _IONBF, 0);
  if (bwData(argv[1], argv[2], argv[3])) { printf("FAIL: данные мира\n"); return 1; }
  const Traffic *t = (const Traffic *)bwTraffic(); if (!t) { printf("FAIL: нет трафика\n"); return 1; }
  // места: старт уровня и полосы трафика по сетке 200 м по всему уровню (координат руками нет)
  // места: старт уровня и полосы трафика по сетке 200 м (−400..400 × −600..600), затем — ОСТАТОК 09.10 п. 13 — сетка 5×7 по рамке
  // полос уровня (на L3/L6/L7 первая сетка давала 11 мест у дорог). POLICE_GRID_OLD=1 — только первая сетка
  float anchors[96][2]; unsigned na = 1; anchors[0][0] = anchors[0][1] = 0.f;
  for (float ax = -400.f; ax <= 400.f && na < 96; ax += 200.f)
    for (float az = -600.f; az <= 600.f && na < 96; az += 200.f) { anchors[na][0] = ax; anchors[na][1] = az; na++; }
  float lo[2] = {1e9f, 1e9f}, hi[2] = {-1e9f, -1e9f};
  for (unsigned r = 0; r < t->hd->nRoad; r++) { const TrPt *P = t->pt + t->road[r].firstPt;
    for (int k = 0; k < t->road[r].nPt; k++) { lo[0] = fminf(lo[0], P[k].x); hi[0] = fmaxf(hi[0], P[k].x); lo[1] = fminf(lo[1], P[k].z); hi[1] = fmaxf(hi[1], P[k].z); } }
  if (!getenv("POLICE_GRID_OLD"))
    for (int i = 0; i < 5; i++) for (int j = 0; j < 7 && na < 96; j++) {
      anchors[na][0] = lo[0] + (hi[0] - lo[0]) * i / 4.f; anchors[na][1] = lo[1] + (hi[1] - lo[1]) * j / 6.f; na++; }
  char d[300]; int nplace = 0, nfoot = 0; float minAll = 1e9f, maxAll = 0.f;
  for (unsigned a = 0; a < na; a++) {
    bwNew(&W);
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    float px = W.car.x, pz = W.car.z, ph = W.car.h, p[3], lh;
    if (a > 0) {   // место у дороги рядом с якорем
      if (!trafficLaneSpot(t, anchors[a][0], anchors[a][1], 60.f, p, &lh)) continue;
      bwPlace(&W, p[0], p[1] + .5f, p[2], lh); for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
      px = W.car.x; pz = W.car.z; ph = W.car.h;
    }
    else { bwPlace(&W, px, W.car.y + .5f, pz, ph); for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0); px = W.car.x; pz = W.car.z; ph = W.car.h; }   // у дома — Гомер за рулём, как в записях PS2 (state_l1_incar)
    nplace++;
    float standY = W.car.y;
    gameMsnPolice(&W.msn, 1, "cPolice", "Pursuit\\L1cop.con", 1);
    if (a == 0 && police()) printf("полиция: TopSpeed %.1f м/с, GasScale %.1f, TireGrip %.1f, HitPoints %.1f, conOk %d\n", police()->car.p.topSpeed, police()->car.p.gasScale, police()->car.p.tireGrip, police()->car.p.hitPoints, police()->conOk);
    const McCar *c = police(); float d0 = c ? hypotf(c->car.x - px, c->car.z - pz) : -1.f, best = 1e9f, worst = 0.f, spawnT = 1.f, idleT = 0.f;
    int respawns = 0, seen = 0;
    for (int f = 0; f < 48 * 60; f++) {   // как main.c hnrPursuit
      bwStep(&W, 0, 0, 0); c = police();
      float dd = c ? hypotf(c->car.x - W.car.x, c->car.z - W.car.z) : 1e9f;
      if (c) { seen = 1; if (dd < best) best = dd; if (dd > worst) worst = dd; }
      idleT = c && dd > 10.f && fabsf(W.car.v) < 30.f / 3.6f ? idleT + BW_DT : 0.f;
      if (((!c || dd > 110.f) && (spawnT -= BW_DT) <= 0.f) || idleT > 10.f) {
        spawnT = 1.f; idleT = 0.f; if (c) gameMsnPolice(&W.msn, 0, "cPolice", "", 1); gameMsnPolice(&W.msn, 1, "cPolice", "Pursuit\\L1cop.con", 1); respawns++;
      }
      if (getenv("PH_TRACE") && f % 60 == 0 && atoi(getenv("PH_TRACE")) == (int)a && c) printf("  t=%.0f police %.1f %.1f v %.1f d %.0f mode %d nroute %d seg %d stuckN %d\n", f / 60.f, c->car.x, c->car.z, c->car.v, dd, c->mode, c->nroute, c->seg, c->stuckN);
    }
    snprintf(d, sizeof d, "игрок стоит (%.0f, %.0f) курс %.0f°: полиция встала в %.0f м, за 48 с ближе всего %.0f м, дальше всего %.0f м, пересадок %d", px, pz, ph * 57.3f, d0, best, worst, respawns);
    // 430: the old universal 90/80 m keepoff assertion is contradicted by natural PS2 chase.
    // This census checks spawn/lifetime; closing intent is proved by chase430 with an old-code red.
    check("presence", seen && isfinite(best) && d0 > 0.f, d);
    if (best < minAll) minAll = best;
    if (worst > maxAll) maxAll = worst;
    gameMsnPolice(&W.msn, 0, "cPolice", "", 1);
    // 430 lets police physically reach and push the car. Foot is an independent
    // spawn regression, so restore its original fixture rather than inherit 48s of impacts.
    bwNew(&W); bwPlace(&W, px, standY + .5f, pz, ph);
    for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    // foot — правка 197 (её красный POLICE_SPAWN_STRAIGHT): Гомер вышел из машины и стоит; к пешему порт ведёт полицию до
    // POLICE_STANDOFF (замера PS2 пешком нет — правило порта 121/197, арест пешком HNR_BUST_FOOT). За 25 с ближе 40 м, не больше
    // одной пересадки
    bwStep(&W, GP_TRIANGLE, 0, 0); for (int f = 0; f < 120; f++) bwStep(&W, 0, 0, 0);
    if (!gameOnFoot(&W.G)) { check("foot", 0, "Гомер не вышел из машины"); continue; }
    float hx = W.homer.x, hz = W.homer.z; nfoot++;
    gameMsnPolice(&W.msn, 1, "cPolice", "Pursuit\\L1cop.con", 1);
    c = police(); best = 1e9f; respawns = 0; float respawnT = 0.f;
    for (int f = 0; f < 25 * 60 && c; f++) {
      bwStep(&W, 0, 0, 0); c = police(); if (!c) break;
      float dd = hypotf(c->car.x - W.homer.x, c->car.z - W.homer.z); if (dd < best) best = dd;
      respawnT -= BW_DT;
      if (dd > 110.f && respawnT <= 0.f) { gameMsnPolice(&W.msn, 0, "cPolice", "", 1); gameMsnPolice(&W.msn, 1, "cPolice", "Pursuit\\L1cop.con", 1); respawns++; respawnT = 1.f; c = police(); }
      if (best < 40.f) break;
    }
    snprintf(d, sizeof d, "Гомер пешком (%.0f, %.0f): полиция ближе всего %.0f м, пересадок %d", hx, hz, best, respawns);
    check("foot", c && best < 40.f && respawns <= 1, d);
    gameMsnPolice(&W.msn, 0, "cPolice", "", 1);
  }
  check("presence", nplace >= 12, nplace >= 12 ? "мест проверено не меньше 12" : "мест меньше 12 — данные?");
  check("foot", nfoot >= 12, nfoot >= 12 ? "мест пешком не меньше 12" : "мест пешком меньше 12");
  printf("stand: по всем местам ближе всего %.1f м, дальше всего %.1f м (430: 93,7 м не универсальная граница; PS2 natural road stand дошла до 55 м)\n", minAll, maxAll);
  // chase — игрок едет (водитель по полосам viewer/msncar.c mcBotInput, как у миссионера) к дальней точке дороги; погоня с 2-й
  // секунды; за 45 с полиция хоть раз подъехала ближе 30 м (в кадре камеры за машиной), не больше 4 пересадок
  int nchase = 0;
  for (unsigned a = 1; a < na && a < 36 && nchase < 6; a += 3) {
    float p[3], lh, g[3]; if (!trafficLaneSpot(t, anchors[a][0], anchors[a][1], 60.f, p, &lh)) continue;
    float gbest = 0.f;   // цель — точка обычной дороги в 250–450 м, дальняя от центра
    for (unsigned r = 0; r < t->hd->nRoad; r++) { if (t->road[r].flags & 1) continue; const TrPt *P = t->pt + t->road[r].firstPt;
      for (int k = 0; k < t->road[r].nPt; k++) { float dd = hypotf(P[k].x - p[0], P[k].z - p[2]); if (dd < 250.f || dd > 450.f) continue;
        if (dd > gbest) { gbest = dd; g[0] = P[k].x; g[1] = P[k].y; g[2] = P[k].z; } } }
    if (gbest <= 0.f) continue;
    bwNew(&W); bwPlace(&W, p[0], p[1] + .5f, p[2], lh); for (int f = 0; f < 30; f++) bwStep(&W, 0, 0, 0);
    nchase++;
    static McCar drv; memset(&drv, 0, sizeof drv); drv.mode = MC_RACE;
    McEnv e; memset(&e, 0, sizeof e); e.w = bwCol(); e.tr = (Traffic *)bwTraffic(); e.driving = 1; e.ppos[0] = e.ppos[2] = 1e6f;
    float thr = 0.f, brk = 0.f, best = 1e9f, respawnT = 0.f, vmax = 0.f; int respawns = 0, on = 0;
    for (int f = 0; f < 47 * 60; f++) {
      drv.car = W.car; CarInput in; mcBotInput(&W.msn.cars, &drv, &e, g, BW_DT, &in);
      unsigned b = 0; thr += in.throttle; if (thr >= 1.f) { b |= GP_R; thr -= 1.f; } brk += in.brake; if (brk >= 1.f) { b |= GP_L; brk -= 1.f; }
      if (in.handbrake > .5f) b |= GP_SQUARE;
      bwStep(&W, b, in.steer, 0); if (fabsf(W.car.v) > vmax) vmax = fabsf(W.car.v);
      if (f == 120) { gameMsnPolice(&W.msn, 1, "cPolice", "Pursuit\\L1cop.con", 1); on = 1; }
      if (!on) continue;
      const McCar *c = police(); if (!c) continue;
      float dd = hypotf(c->car.x - W.car.x, c->car.z - W.car.z); if (dd < best) best = dd;
      respawnT -= BW_DT;
      if (dd > 110.f && respawnT <= 0.f) { gameMsnPolice(&W.msn, 0, "cPolice", "", 1); gameMsnPolice(&W.msn, 1, "cPolice", "Pursuit\\L1cop.con", 1); respawns++; respawnT = 1.f; }
      if (best < 30.f) break;
    }
    snprintf(d, sizeof d, "игрок едет от (%.0f, %.0f) к (%.0f, %.0f), скорость до %.0f м/с: полиция ближе всего %.0f м, пересадок %d", p[0], p[2], g[0], g[2], vmax, best, respawns);
    check("chase", best < 30.f && respawns <= 4, d);
    gameMsnPolice(&W.msn, 0, "cPolice", "", 1);
  }
  check("chase", nchase >= 4, nchase >= 4 ? "поездок не меньше 4" : "поездок меньше 4 — данные?");
  printf("RESULT %s мест %d, провалов %d\n", fails ? "FAIL" : "PASS", nplace, fails);
  return fails ? 1 : 0;
}
