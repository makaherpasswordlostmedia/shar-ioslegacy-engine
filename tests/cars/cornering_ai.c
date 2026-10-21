// Машины ИИ и миссий в повороте (аудит 09.10 п. 49: перевороты машин ИИ не покрыты проверками). Все пары «кузов, .con водителя» из
// AddStageVehicle миссий уровней 1–7 (build/missions/level0N.msn), параметры — как в игре (carParamsForAi, msncar.c mcSpawn).
// Тот же заезд, что tests/cars/cornering.c (ровная площадка, разгон 10 с, полный руль с газом 6 с и отдельно с ручником), плюс
// направление крена (как attitude.c A: 15 м/с, руль ±0,5). Печатает по паре; итог «RESULT cases N flips F two-wheel T inward I».
//   cc -std=c11 -O2 -I viewer tests/cars/cornering_ai.c viewer/car.c viewer/col.c viewer/mission/msn_file.c viewer/mission/msn_ops.c -lm -o cornering_ai
//   ./cornering_ai build/missions/level01.msn … [--max-flips N] [--max-inward N]   (код выхода 1, если больше)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "mission/msn.h"
static struct { ColHdr h; ColTri t[2]; unsigned start[2], refs[2]; } fl;
static ColWorld W;
typedef struct { char name[16], con[48]; } Pair;
static Pair P[512]; static int np;
static void add(const char *n, const char *c) {
  if (!n || !c || !*c || !strcmp(c, "NULL")) return;
  for (int i = 0; i < np; i++) if (!strcasecmp(P[i].name, n) && !strcasecmp(P[i].con, c)) return;
  if (np < 512) { snprintf(P[np].name, 16, "%s", n); snprintf(P[np].con, 48, "%s", c); np++; }
}
static void scan(const char *path) {
  FILE *f = fopen(path, "rb"); if (!f) { printf("нет %s\n", path); exit(2); }
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *d = malloc(n); if (fread(d, 1, n, f) != (size_t)n) exit(2); fclose(f);
  static MsnFile F; char err[160]; if (msn_open(&F, d, n, err, sizeof err)) { printf("%s: %s\n", path, err); exit(2); }
  for (unsigned i = 0; i < F.ncmds; i++) { const MsnCmd *c = &F.cmds[i]; if (c->op == MSN_OP_ADDSTAGEVEHICLE) add(msn_arg_s(&F, c, 0), msn_arg_s(&F, c, 3)); }
}
int main(int argc, char **argv) {
  int maxFlips = -1, maxIn = -1;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--max-flips") && i + 1 < argc) maxFlips = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--max-inward") && i + 1 < argc) maxIn = atoi(argv[++i]);
    else scan(argv[i]);
  }
  memset(&fl, 0, sizeof fl); memcpy(fl.h.magic, "COL1", 4); fl.h.ox = fl.h.oz = -2000; fl.h.cell = 4000; fl.h.W = fl.h.H = 1; fl.h.ntri = fl.h.nref = 2;
  fl.t[0] = (ColTri){{-2000, 0, -2000}, {2000, 0, 2000}, {2000, 0, -2000}, {0, 1, 0}};
  fl.t[1] = (ColTri){{-2000, 0, -2000}, {-2000, 0, 2000}, {2000, 0, 2000}, {0, 1, 0}};
  fl.start[1] = 2; fl.refs[0] = 0; fl.refs[1] = 1; if (colInit(&W, &fl, sizeof fl)) return 2;
  const float dt = 1.f / 30.f; int nflip = 0, ntwo = 0, ncase = 0, nin = 0, nocon = 0;
  for (int i = 0; i < np; i++) {
    CarParams p; if (!carParamsForAi(P[i].con, P[i].name, &p)) { nocon++; continue; }
    for (int mode = 0; mode < 2; mode++) {
      Car c; carInit(&c, &p, &W, 0, 0, 0, 0); CarInput in = {1.f, 0.f, 0.f, 0.f};
      for (int f = 0; f < 30 * 10; f++) carUpdate(&c, &W, &in, dt);
      float vin = c.v, rollMax = 0.f; int two = 0, n = 0, flip = 0, r0 = c.rights;
      in.steer = 1.f; if (mode) in.handbrake = 1.f;
      for (int f = 0; f < 30 * 6; f++) {
        carUpdate(&c, &W, &in, dt); n++;
        float up = 1.f - 2.f * (c.q[1] * c.q[1] + c.q[3] * c.q[3]); float roll = fabsf(c.roll) * 57.2958f; if (roll > rollMax) rollMax = roll;
        two += c.wheels <= 2; if (up < 0.f) flip = 1;
      }
      flip |= c.rights - r0 > 0; nflip += flip; ntwo += two * 10 > n; ncase++;
      if (flip || two * 10 > n) printf("%-9s %-34s %-6s v_in %5.1f крен %5.1f на двух %4.1f%% %s\n", p.name, P[i].con, mode ? "ebrake" : "gas", vin * 3.6f, rollMax, 100.f * two / n, flip ? "FLIP" : "");
    }
    for (int s = -1; s <= 1; s += 2) {   // направление крена
      Car c; carInit(&c, &p, &W, 0, 0, 0, 0); CarInput in = {1, 0, 0, 0};
      for (int f = 0; f < 50 * 20 && hypotf(c.vel[0], c.vel[2]) < 15.f; f++) carUpdate(&c, &W, &in, 1 / 50.f);
      in.steer = .5f * s; float va[3]; memcpy(va, c.vel, sizeof va); double st = 0; int k = 0;
      for (int f = 0; f < 100; f++) {
        in.throttle = hypotf(c.vel[0], c.vel[2]) < 15.f ? 1.f : 0.f; carUpdate(&c, &W, &in, 1 / 50.f);
        float ax = (c.vel[0] - va[0]) * 50.f, az = (c.vel[2] - va[2]) * 50.f, al = hypotf(ax, az); memcpy(va, c.vel, sizeof va);
        const float *q = c.q; float ux = 2.f * (q[1] * q[2] - q[0] * q[3]), uz = 2.f * (q[2] * q[3] + q[0] * q[1]);
        if (f >= 50 && al > 3.f) { st += asinf(fmaxf(-1.f, fminf(1.f, (ux * ax + uz * az) / al))) * 57.2958f; k++; }
      }
      if (k && st / k > .05f) { nin++; printf("%-9s %-34s крен ВНУТРЬ %+.2f°\n", p.name, P[i].con, st / k); }
    }
  }
  printf("пар кузов+.con %d (без .con %d)\n", np, nocon);
  printf("RESULT cases %d flips %d two-wheel>10%% %d inward %d\n", ncase, nflip, ntwo, nin);
  return (maxFlips >= 0 && nflip > maxFlips) || (maxIn >= 0 && nin > maxIn);
}
