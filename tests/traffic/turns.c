// №400 (Роб 08.10: «машины трафика поворачивают не по живому»): снос задней оси машин трафика на настоящих данных уровня.
// Живая колёсная машина катится: скорость задней оси идёт вдоль кузова (снос ~0°). Прежнее правило (центр на кривой, нос на
// точку в 4 м) заворачивало кузов раньше хода — задняя ось ехала боком. Те же пять точек и 900 кадров, что tests/traffic/host.c
// (уровни 2, 3, 5, 6 — TURNS_DATA_SPOTS=1: начала полос). «Отход от полосы» при новой схеме мал по построению (центр на полосе) —
// стены и землю под машинами проверяет tests/traffic/host.sh; рывок угловой скорости — p99.
//   tests/traffic/turns.sh [level.shr] [traffic.shr]   -> строка PASS/FAIL; красный: -DTRAFFIC_TURN_OLD обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"
static ColWorld world; static Traffic T; static Car player;
static const float DT = 1.f / 30.f;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) {
  unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u);
  fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; }
  return m;
}
static float ground(float x, float z, float y) { float g; return colGround(&world, x, z, y + 2.f, y - 50.f, &g, 0) ? g : y; }
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
  long n = 0, over5 = 0, over10 = 0; double worst = 0., offMax = 0., jerkMax = 0.; static float hist[100000], offs[100000], jerks[100000]; int nh = 0, no = 0, nj = 0;
  float spot[5][2]; int nspot = 5;   // уровень 1 (и 4, 7 — тот же город): точки host.c; иначе — начала полос из данных уровня
  for (int a = 0; a < 5; a++) { spot[a][0] = at[a][0]; spot[a][1] = at[a][1]; }
  if (getenv("TURNS_DATA_SPOTS")) for (int a = 0; a < 5; a++) {
    const TrRoad *r = &T.road[(a * T.hd->nRoad) / 5]; const TrPt *P = &T.pt[r->firstPt]; spot[a][0] = P->x; spot[a][1] = P->z; }
  for (int a = 0; a < nspot; a++) {
    carInit(&player, NULL, &world, spot[a][0], ground(spot[a][0], spot[a][1], 50.f), spot[a][1], 0.f);
    trafficReset(&T, &world);
    float px[TR_MAXCAR], pz[TR_MAXCAR], hp[TR_MAXCAR], wp[TR_MAXCAR]; int have[TR_MAXCAR] = {0};
    for (int fr = 0; fr < 900; fr++) {
      CarInput ci = {0, 0, 0, 1}; carUpdate(&player, &world, &ci, DT);
      float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3.f, player.z - 7.f}, fw[3] = {0, 0, 1};
      trafficUpdate(&T, &world, &player, 1, pp, eye, fw, DT);
      TrEvent e; while (trafficPopEvent(&T, &e)) {}
      for (int i = 0; i < T.maxCars; i++) {
        const TrCar *c = &T.car[i]; const Car *k = &c->car;
        if (c->mode != TRM_DRIVE) { have[i] = 0; continue; }
        float fx = sinf(k->h), fz = cosf(k->h), rx = k->x - fx * k->p.wheelR, rz = k->z - fz * k->p.wheelR;
        if (have[i]) {
          float vx = (rx - px[i]) / DT, vz = (rz - pz[i]) / DT, sp = sqrtf(vx * vx + vz * vz);
          if (sp > 2.f && sp < 40.f) {
            float slip = fabsf(atan2f(-vx * fz + vz * fx, vx * fx + vz * fz)) * 57.2958f;   // угол скорости оси к кузову
            if (slip > 90.f) slip = 180.f - slip;
            n++; over5 += slip > 5.f; over10 += slip > 10.f; if (slip > worst) worst = slip; if (nh < 100000) hist[nh++] = slip;
          }
        }
        // отход от полосы: начало машины против середины колёсной базы на маршруте (независимо от того, как поставлен кузов)
        { float mid[3]; trafficRoutePoint(&T, c, (k->p.wheelF - k->p.wheelR) * .5f, mid);
          float ox = k->x - mid[0], oz = k->z - mid[2], o = sqrtf(ox * ox + oz * oz); if (o > offMax) offMax = o; if (no < 100000) offs[no++] = o; }
        float mv = have[i] ? sqrtf((rx - px[i]) * (rx - px[i]) + (rz - pz[i]) * (rz - pz[i])) : 0.f;
        if (have[i] && mv > c->v * DT * 2.f + .5f) have[i] = 0;   // машина появилась заново в этом месте списка — не поворот
        if (have[i]) { float w = (k->h - hp[i]); while (w > 3.14159f) w -= 6.28318f; while (w < -3.14159f) w += 6.28318f; w /= DT;
          if (have[i] > 1) { float j = fabsf(w - wp[i]) / DT; if (c->v > 1.f) { if (j > jerkMax) jerkMax = j; if (nj < 100000) jerks[nj++] = j; } } wp[i] = w; }
        hp[i] = k->h;
        px[i] = rx; pz[i] = rz; have[i] = have[i] ? 2 : 1;
      }
    }
  }
  for (int i = 1; i < nh; i++) { float v = hist[i]; int j = i - 1; while (j >= 0 && hist[j] > v) { hist[j + 1] = hist[j]; j--; } hist[j + 1] = v; }
  float p99 = nh ? hist[(int)(nh * .99f)] : 0.f, p95 = nh ? hist[(int)(nh * .95f)] : 0.f;
  for (int i = 1; i < no; i++) { float v = offs[i]; int j = i - 1; while (j >= 0 && offs[j] > v) { offs[j + 1] = offs[j]; j--; } offs[j + 1] = v; }
  for (int i = 1; i < nj; i++) { float v = jerks[i]; int j = i - 1; while (j >= 0 && jerks[j] > v) { jerks[j + 1] = jerks[j]; j--; } jerks[j + 1] = v; }
  float o99 = no ? offs[(int)(no * .99f)] : 0.f, j99 = nj ? jerks[(int)(nj * .99f)] : 0.f;
  int ok = n > 2000 && p99 <= 5.f && over10 * 1000 <= n && o99 <= .85f && j99 <= 40.;   // отход: запас полосы до колеса (1,75 − 0,9 м); максимум печатается
  printf("%s traffic turns: samples %ld, rear-axle slip p95 %.2f°, p99 %.2f°, max %.1f°, >5° %ld, >10° %ld; off lane p99 %.2f max %.2f m; yaw accel p99 %.1f max %.1f rad/s2\n",
         ok ? "PASS" : "FAIL", n, p95, p99, worst, over5, over10, o99, offMax, j99, jerkMax);
  return ok ? 0 : 1;
}
