// V112: after-impact physical cars do not resume lane-driving. Historical №400 gate under REJOIN_HISTORIC
// Задняя ось №400 тянется за началом машины; если ось осталась от езды ДО удара, а машину отбросило назад, ось оказывалась впереди
// точки полосы и курс «от оси к началу» разворачивался на 180°: машина ехала задом наперёд, скорость кузова против хода.
// Настоящие данные уровня, те же пять точек, что tests/traffic/turns.c; удар — искусственный толчок (каждую едущую машину на кадре
// 300 и 600: ТРМ_PHYS, скорость назад вдоль кузова SHOVE м/с, как от лобового удара), дальше настоящие physStep -> backToLane ->
// driveStep. Меряется: кадры едущей машины, у которой курс кузова дальше 90° от хода маршрута (точка 0 -> LOOK), и наибольший
// поворот кузова за кадр в первые 2 с после возврата на полосу.
//   tests/traffic/rejoin.sh [level.shr] [traffic.shr]   -> строка PASS/FAIL; красный: -DTRAFFIC_REJOIN_REAR_OLD обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"
static ColWorld world; static Traffic T; static Car player;
static const float DT = 1.f / 30.f;
#ifndef SHOVE
#define SHOVE 6.f
#endif
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u);
  fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; }
  return m;
}
static float ground(float x, float z, float y) { float g; return colGround(&world, x, z, y + 2.f, y - 50.f, &g, 0) ? g : y; }
static float wrapPi(float a) { while (a > 3.14159265f) a -= 6.2831853f; while (a < -3.14159265f) a += 6.2831853f; return a; }
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr", *trf = argc > 2 ? argv[2] : "build/traffic.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) return 2;
  unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104 || memcmp(hdr, "SHR7", 4)) return 2;
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned fsize = (unsigned)ftell(f), end = fsize;
  if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f);
  if (!cm || colInit(&world, cm, end - colOff)) return 2;
  FILE *g = fopen(trf, "rb"); if (!g) return 2;
  fseek(g, 0, SEEK_END); unsigned tsize = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, tsize); fclose(g);
  if (!buf || trafficInitMem(&T, buf, tsize, 0)) return 2;
  static const float at[5][2] = {{220.f, 172.f}, {209.f, 285.f}, {193.8f, 570.f}, {-11.f, 586.f}, {209.f, 279.f}};
  float spot[5][2];
  for (int a = 0; a < 5; a++) { spot[a][0] = at[a][0]; spot[a][1] = at[a][1]; }
  if (getenv("TURNS_DATA_SPOTS")) for (int a = 0; a < 5; a++) {
    const TrRoad *r = &T.road[(a * T.hd->nRoad) / 5]; const TrPt *P = &T.pt[r->firstPt]; spot[a][0] = P->x; spot[a][1] = P->z; }
  long frames = 0, rev = 0; int shoved = 0, rejoined = 0; float worstTurn = 0.f;
  for (int a = 0; a < 5; a++) {
    carInit(&player, NULL, &world, spot[a][0], ground(spot[a][0], spot[a][1], 50.f), spot[a][1], 0.f);
    trafficReset(&T, &world);
    int prevMode[TR_MAXCAR]; float since[TR_MAXCAR], hp[TR_MAXCAR];
    for (int i = 0; i < TR_MAXCAR; i++) { prevMode[i] = TRM_OFF; since[i] = 1e9f; hp[i] = 0.f; }
    for (int fr = 0; fr < 1200; fr++) {
      if (fr == 300 || fr == 600) for (int i = 0; i < T.maxCars; i++) {
        TrCar *c = &T.car[i]; if (c->mode != TRM_DRIVE) continue;
        Car *k = &c->car; k->vel[0] = -sinf(k->h) * SHOVE; k->vel[2] = -cosf(k->h) * SHOVE; k->v = -SHOVE; k->w[1] = 0.f;
        c->mode = TRM_PHYS; c->stillT = 0.f; shoved++;
      }
      CarInput ci = {0, 0, 0, 1}; carUpdate(&player, &world, &ci, DT);
      float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3.f, player.z - 7.f}, fw[3] = {0, 0, 1};
      trafficUpdate(&T, &world, &player, 1, pp, eye, fw, DT);
      TrEvent e; while (trafficPopEvent(&T, &e)) {}
      for (int i = 0; i < T.maxCars; i++) {
        const TrCar *c = &T.car[i]; const Car *k = &c->car;
        if (c->mode == TRM_DRIVE && prevMode[i] == TRM_PHYS) { since[i] = 0.f; rejoined++; }
        if (c->mode == TRM_DRIVE) {
          float p0[3], p1[3]; trafficRoutePoint(&T, c, 0.f, p0); trafficRoutePoint(&T, c, 4.f, p1);
          float dx = p1[0] - p0[0], dz = p1[2] - p0[2];
          if (dx * dx + dz * dz > .01f) { frames++; if (fabsf(wrapPi(k->h - atan2f(dx, dz))) > 1.5708f) rev++; }
          if (since[i] > 0.f && since[i] < 2.f && prevMode[i] == TRM_DRIVE) { float d = fabsf(wrapPi(k->h - hp[i])); if (d > worstTurn) worstTurn = d; }
          since[i] += DT;
        }
        hp[i] = k->h; prevMode[i] = c->mode;
      }
    }
  }
  // курс по ходу: ни одного кадра задом наперёд (поворот кузова за кадр после возврата — печатается для сведения)
#ifdef REJOIN_HISTORIC
  int ok = shoved > 20 && rejoined > 10 && frames > 2000 && rev == 0;
#else
  // V112 replaced the unsupported restart requirement; OLD must return and fail
  int ok = shoved > 20 && rejoined == 0 && frames > 2000 && rev == 0;
#endif
  printf("%s traffic rejoin: shoved %d, back on lane %d, drive frames %ld, reversed (>90° from route) %ld, max body turn per frame in 2 s after rejoin %.2f rad\n",
         ok ? "PASS" : "FAIL", shoved, rejoined, frames, rev, worstTurn);
  return ok ? 0 : 1;
}
