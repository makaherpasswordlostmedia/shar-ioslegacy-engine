// pilot — хост-проверка автопилота теста (viewer/smkpilot.h): машина L1 едет по сети дорог 60 с, печатает дистанцию и сколько раз застряла.
//   pilot LEVEL PLAYER MSN SECS [SEED]   — выход 1, если дистанция < 500 м за 60 с или застряла
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "world.h"
#include "smkpilot.h"
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 5 || bwData(argv[1], argv[2], argv[3])) { fprintf(stderr, "usage: pilot LEVEL PLAYER MSN SECS [SEED]\n"); return 2; }
  float secs = (float)atof(argv[4]); unsigned seed = argc > 5 ? (unsigned)atoi(argv[5]) : 1;
  bwNew(&W); Traffic *t = (Traffic *)bwTraffic(); if (!t || !t->hd) { printf("нет трафика\n"); return 2; }
  if (getenv("PILOT_WALK")) {   // пешком: Гомер по путям пешеходов трафика
    SmkWalk Wk; smkWalkInit(&Wk); Wk.props = &W.props; Wk.sp = &W.sp; for (int f = 0; f < 30; f++) bwStep(&W, 0, 0.f, 0.f); float x0 = W.homer.x, z0 = W.homer.z, tx = 0, tz = 0;
    for (int f = 0; f < (int)(secs * 60); f++) {
      if (!smkWalkStep(&Wk, t, W.homer.x, W.homer.z, 1.f / 60.f, &tx, &tz)) { bwStep(&W, 0, 0.f, 0.f); continue; }
      float r = atan2f(tx - W.homer.x, tz - W.homer.z) - W.homer.camYaw; bwStep(&W, GP_CIRCLE, -sinf(r), -cosf(r));
      if (getenv("PILOT_V") && f % 30 == 0 && f < 1500) printf("   f%d h(%.1f,%.1f) цель(%.1f,%.1f) path %d idx %d\n", f, W.homer.x, W.homer.z, tx, tz, Wk.path, Wk.idx);
      if (f % 600 == 599) printf("  t=%.0f с: дистанция %.0f м, разворотов %d, путь %d точка %d\n", (f + 1) / 60.f, Wk.dist, Wk.stuckN, Wk.path, Wk.idx);
    }
    printf("ИТОГ пешком: за %.0f с прошёл %.0f м (по прямой %.0f м), разворотов %d\n", secs, Wk.dist, hypotf(W.homer.x - x0, W.homer.z - z0), Wk.stuckN);
    return Wk.dist < 40.f;
  }
  float lowT = 0, runT = 0, maxRun = 0; CarInput lastIn = {0}; SmkPilot P; smkPilotInit(&P, seed, 16.f); P.props = &W.props; P.sp = &W.sp;
  { float gy, sx = 220.f, sz = 172.f, sh = 1.5708f, y0 = 50.f;   // спавн L1, игрок в машине; PILOT_AT=x,z,y0,h — другое место (y0 — высота, от которой ищется земля вниз)
    if (getenv("PILOT_AT")) sscanf(getenv("PILOT_AT"), "%f,%f,%f,%f", &sx, &sz, &y0, &sh);
    colGround(bwCol(), sx, sz, y0, -1e6f, &gy, 0); bwPlace(&W, sx, gy + .3f, sz, sh); }
  for (int f = 0; f < 60; f++) bwStep(&W, 0, 0.f, 0.f);
  P.lx = W.car.x; P.lz = W.car.z; float x0 = W.car.x, z0 = W.car.z;
  for (int f = 0; f < (int)(secs * 60); f++) {
    if (getenv("PILOT_V") && P.stuckT > 1.4f && P.stuckT < 1.43f) printf("  стоит с %.1fs: (%.1f,%.1f) h %.2f v %.2f n %d seg %d цель (%.0f,%.0f) руль %.2f газ %.1f why %d\n", f / 60.f, W.car.x, W.car.z, W.car.h, W.car.v, P.n, P.seg, P.goal[0], P.goal[2], lastIn.steer, lastIn.throttle, P.why);
    int sn0 = P.stuckN; CarInput in; smkPilotStep(&P, t, &W.car, 1.f / 60.f, &in);
    if (P.stuckN != sn0 && getenv("PILOT_V")) printf("  застряла на %.1fs: (%.1f,%.1f,%.1f) h %.2f, стена %d:%u, цель (%.0f,%.0f), seg %d/%d\n", f / 60.f, W.car.x, W.car.y, W.car.z, W.car.h, W.car.wallType, W.car.wallIdx, P.goal[0], P.goal[2], P.seg, P.n);
    if (getenv("PILOT_V") && P.stuckT > 1.4f && P.stuckT < 1.43f) { SmkObs ob[SMK_OBS_MAX]; int no = spGather(t, &W.props, &W.sp, W.car.x, W.car.z, 7.f, .6f, &W.car, ob); for (int i = 0; i < no; i++) printf("     преп (%.1f,%.1f) r %.1f\n", ob[i].x, ob[i].z, ob[i].r); }
    unsigned b = 0; if (in.throttle > .5f) b |= GP_R; if (in.brake > .1f) b |= GP_L; if (in.handbrake > .5f) b |= GP_SQUARE;
    lastIn = in; bwStep(&W, b, in.steer, 0.f);
    if (fabsf(W.car.v) < 1.f) { lowT += 1.f / 60; runT += 1.f / 60; if (runT > maxRun) maxRun = runT; } else runT = 0;
    if (f % 600 == 599) printf("  t=%.0f с: дистанция %.0f м, застреваний %d, целей %d, планов %d, v %.1f\n", (f + 1) / 60.f, P.dist, P.stuckN, P.goals, P.plans, W.car.v);
  }
  printf("СТОЯЛА: %.1f с (|v|<1), самая долгая остановка %.1f с\n", lowT, maxRun);
  printf("ИТОГ: за %.0f с проехала %.0f м (от старта по прямой %.0f м), застреваний %d, целей %d, урон %.2f\n", secs, P.dist, hypotf(W.car.x - x0, W.car.z - z0), P.stuckN, P.goals, W.car.damage);
  return (secs >= 60.f && P.dist < 500.f) || P.stuckN > 0;
}
