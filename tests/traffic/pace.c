// Аудит 09.10 п. 22: ход машины трафика против трасс близнеца PS2 tw_v14_* (tools/research/traffic22/minivan_pace.py).
// Те же места, что минивэн записи (координаты порта): (1) прямая z 156 от x 234 к перекрёстку у x ~205 (PS2: 17,1 м/с, тормозит
// от ~22 м до остановки, 5,5–7,0 м/с², стоит); (2) изгиб дороги 45 у (158, 92) -> (170, 94) (PS2: 17,0–17,7 м/с при поперечном до
// 13,5 м/с²; стоящие машины и прохожие на этом прогоне убраны — проверяется правило поворота). Игрок стоит в стороне (не мешает). Проверки (числа записи, допуск по разбросу замеров):
//   cruise — на прямой до торможения 15,8..18,8 м/с (PS2 медиана 17,3, разброс 16,3–18,0; данные дороги 13,9);
//   brake  — среднее замедление от начала торможения до остановки 4..8,5 м/с² (PS2: 17,1 -> 4,0 за 2,4 с = 5,5; 15,7 -> 5,9 за 1,4 с
//            = 7,0; начало ~22 м до остановки), наибольшее за 0,2 с ≤ 8,5 (порт прежде — 12);
//   stop   — машина останавливается у перекрёстка (PS2 стоит);
//   bend   — на изгибе дороги 45 не медленнее 15 м/с (PS2 16,9–17,7 при поперечном до 13,5 м/с²).
// Гейт (ОСТАТОК 09.10 п. 17): красный tests/traffic/pace.sh — -DTRAFFIC_PACE_OLD=1 обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"
static ColWorld world; static Traffic T; static Car player;
static int fails;
static void check(const char *n, int ok, const char *d) { printf("CHECK %-7s %s  %s\n", n, ok ? "OK  " : "FAIL", d); if (!ok) fails++; }
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) { unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m; }
static float ground(float x, float z, float y) { float g; return colGround(&world, x, z, y + 2.f, y - 50.f, &g, 0) ? g : y; }
#define NS 600
static float vs[NS], xs[NS];
static int run(float x0, float z0, float h0, float v0, float px, float pz, int nopark) {   // кадры 1/60 с, запись скорости и x машины 0
  carInit(&player, NULL, &world, px, ground(px, pz, 50.f), pz, 0.f);
  trafficReset(&T, &world);
  int np = T.npark, mp = T.maxPeds;   // изгиб: только правило поворота — без стоящих машин (у дороги 45 стоящая тормозит, В58) и прохожих
  if (nopark) { T.npark = 0; for (int i = 0; i < T.maxPeds; i++) T.ped[i].mode = TRP_OFF; T.maxPeds = 0; }
  for (int i = 0; i < T.maxCars; i++) T.car[i].mode = 0;
  if (trafficCarPlace(&T, &world, x0, z0, h0)) return 0;
  T.car[0].v = v0;
  const float DT = 1.f / 60.f;
  for (int fr = 0; fr < NS; fr++) {
    vs[fr] = T.car[0].mode == TRM_DRIVE ? T.car[0].v : -1.f; xs[fr] = T.car[0].car.x;
    CarInput ci = {0, 0, 0, 1}; carUpdate(&player, &world, &ci, DT);
    float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3.f, player.z - 7.f}, fw[3] = {0, 0, 1};
    for (int i = 1; i < T.maxCars; i++) T.car[i].mode = 0;   // только машина 0
    trafficUpdate(&T, &world, &player, 1, pp, eye, fw, DT);
    TrEvent e; while (trafficPopEvent(&T, &e)) {}
  }
  T.npark = np; T.maxPeds = mp;
  return 1;
}
int main(int argc, char **argv) {
  const char *lvl = argc > 1 ? argv[1] : "build/level.shr", *trf = argc > 2 ? argv[2] : "build/traffic.shr";
  FILE *f = fopen(lvl, "rb"); if (!f) return 2; unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104) return 2;
  unsigned pvsOff = *(unsigned *)(hdr + 88), colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96);
  fseek(f, 0, SEEK_END); unsigned end = (unsigned)ftell(f); if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); fclose(f); if (!cm || colInit(&world, cm, end - colOff)) return 2;
  FILE *g = fopen(trf, "rb"); if (!g) return 2; fseek(g, 0, SEEK_END); unsigned ts = (unsigned)ftell(g); unsigned char *buf = readAt(g, 0, ts); fclose(g);
  if (!buf || trafficInitMem(&T, buf, ts, 0)) return 2;
  char d[200];
  // (1) прямая к перекрёстку: машина PS2 появилась на (234, 156) на ходу 17,4 м/с курсом −x ; игрок записи стоял у (215, 170)
  if (!run(234.f, 156.1f, -1.5708f, 17.1f, 215.05f, 170.25f, 0)) { printf("FAIL: нет полосы\n"); return 1; }
  int stopF = -1; for (int i = 0; i < NS; i++) if (vs[i] >= 0.f && vs[i] < .05f) { stopF = i; break; }
  float cruise = vs[30], maxDec = 0.f; int brakeF = -1;
  for (int i = 30; i + 12 < NS && (stopF < 0 || i < stopF); i++) {
    if (brakeF < 0 && vs[i] < cruise - .5f) brakeF = i;
    if (vs[i] >= 0.f && vs[i + 12] >= 0.f) maxDec = fmaxf(maxDec, (vs[i] - vs[i + 12]) / .2f);
  }
  float brakeDist = brakeF >= 0 && stopF >= 0 ? fabsf(xs[brakeF] - xs[stopF]) : -1.f;
  snprintf(d, sizeof d, "скорость на прямой через 0,5 с: %.1f м/с (PS2 медиана 16,5 (№624), 17,3 по минивэну; 15,8..17,0)", cruise); check("cruise", cruise >= 15.8f && cruise <= 17.0f, d);
  float avgDec = brakeDist > 0.f ? cruise * cruise / (2.f * brakeDist) : 99.f;
  snprintf(d, sizeof d, "торможение с %.1f м/с за %.1f м до остановки: среднее %.1f м/с² (PS2 5,5–7,0; 4..8,5), наибольшее за 0,2 с %.1f (PS2 ≤ 7,0; ≤ 8,5)",
           cruise, brakeDist, avgDec, maxDec);
  check("brake", avgDec >= 4.f && avgDec <= 8.5f && maxDec <= 8.5f, d);
  snprintf(d, sizeof d, "остановилась у перекрёстка: %s (x %.1f)", stopF >= 0 ? "да" : "нет", stopF >= 0 ? xs[stopF] : 0.f); check("stop", stopF >= 0, d);
  // (2) изгиб дороги 45: PS2 (158,4; 92,2) курсом ~89° на 17,3 м/с; игрок в 25 м в стороне
  if (!run(158.4f, 92.2f, 1.553f, 17.3f, 160.f, 70.f, 1)) { printf("FAIL: нет полосы 45\n"); return 1; }
  float vmin = 1e9f; for (int i = 0; i < 48; i++) if (vs[i] >= 0.f) vmin = fminf(vmin, vs[i]);
  if (getenv("PACE_DBG")) for (int i = 0; i < 48; i += 6) printf("  %d x %.1f v %.2f\n", i, xs[i], vs[i]);   // 0,8 с — до (170, 94) у PS2
  snprintf(d, sizeof d, "на изгибе дороги 45 за 0,8 с не медленнее %.1f м/с (PS2 16,9–17,7; нужно ≥ 15)", vmin); check("bend", vmin >= 15.f, d);
  printf("RESULT %s провалов %d\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
