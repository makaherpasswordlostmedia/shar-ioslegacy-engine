// №176 повтор (Роб, TEST27: «машина трафика с одного удара на скорости просто взорвалась»): удар машиной игрока (famil_v) по ЕДУЩЕЙ машине трафика настоящего
// уровня: сзади, в бок, в лоб (встречным) на 15/25/35 м/с; урон за удар (4 с после контакта) и разбита ли. Эталон PS2 (knowledge/facts/ps2-traffic-hit.yaml): при 20 и 35 м/с
// в бок минивэн цел; порт на плоском тесте tests/trafhit: 20 → 0,20, 35 → 0,35. Печатает TSV: машина, сторона, v, урон, разбита, откатов подшага, макс. скачок урона за кадр.
// cc -std=c11 -O2 -w -DSKIN_HOST -I viewer tools/cartest/traf_boom.c viewer/traffic.c viewer/col.c viewer/car.c viewer/skin.c viewer/homer.c -lm   ./a.out level.shr traffic.shr [число_машин]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "traffic.h"
static ColWorld world; static Traffic T; static Car player;
static const float DT = 1.f / 30.f;
static unsigned char *readAt(FILE *f, unsigned off, unsigned sz) { unsigned char *m = aligned_alloc(64, (sz + 63) & ~63u); fseek(f, off, SEEK_SET); if (fread(m, 1, sz, f) != sz) { free(m); return 0; } return m; }
static float ground(float x, float z, float top) { float g; return colGround(&world, x, z, top, -1e6f, &g, 0) ? g : 0.f; }
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; unsigned char hdr[104]; if (fread(hdr, 1, 104, f) != 104) return 2;
  unsigned colOff = *(unsigned *)(hdr + 92), propOff = *(unsigned *)(hdr + 96), pvsOff = *(unsigned *)(hdr + 88);
  fseek(f, 0, SEEK_END); unsigned fsize = ftell(f), end = fsize; if (pvsOff > colOff && pvsOff < end) end = pvsOff; if (propOff > colOff && propOff < end) end = propOff;
  unsigned char *cm = readAt(f, colOff, end - colOff); if (!cm || colInit(&world, cm, end - colOff)) return 2;
  FILE *g = fopen(argv[2], "rb"); fseek(g, 0, SEEK_END); unsigned ts = ftell(g); unsigned char *tb = readAt(g, 0, ts);
  if (trafficInitMem(&T, tb, ts, 0)) return 2; T.maxPeds = 0;
  int nTry = argc > 3 ? atoi(argv[3]) : 6; const char *sides[3] = {"zad", "bok", "lob"}; const float vs[3] = {15, 25, 35};
  printf("tcar\tmodel\tside\tv\tdmg\tdestroyed\treverts\tmax_jump\n");
  int worstN = 0; float worst = 0;
  for (int n = 0; n < nTry; n++) for (int s = 0; s < 3; s++) for (int iv = 0; iv < 3; iv++) {
    trafficReset(&T, &world);
    carInit(&player, NULL, &world, 220.f, ground(220.f, 172.f, 50.f), 172.f, 0.f);
    int drv = -1, cnt = 0;
    for (int fr = 0; fr < 240 && drv < 0; fr++) {
      CarInput ci = {0, 0, 0, 1}; carUpdate(&player, &world, &ci, DT);
      float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3, player.z - 7}, fw[3] = {0, 0, 1};
      trafficUpdate(&T, &world, &player, 1, pp, eye, fw, DT);
      for (int i = 0; i < T.maxCars; i++) if (T.car[i].mode == TRM_DRIVE && T.car[i].v > 3.f) { if (cnt++ == n) { drv = i; break; } }
    }
    if (drv < 0) continue;
    TrCar *tc = &T.car[drv]; Car *k = &tc->car;
    float fx = sinf(k->h), fz = cosf(k->h), rx = fz, rz = -fx, sx, sz, h;
    if (s == 0) { sx = k->x - fx * 18.f; sz = k->z - fz * 18.f; h = k->h; }               // сзади, в ту же сторону
    else if (s == 1) { sx = k->x + rx * 18.f; sz = k->z + rz * 18.f; h = atan2f(-rx, -rz); }  // справа, поперёк
    else { sx = k->x + fx * 22.f; sz = k->z + fz * 22.f; h = k->h + 3.14159265f; }        // встречным
    float gy = ground(sx, sz, k->y + 6.f); CarParams cp; const char *pc = getenv("PCAR"); if (pc) { carParamsFor(pc, &cp); carInit(&player, &cp, &world, sx, gy, sz, h); } else carInit(&player, NULL, &world, sx, gy, sz, h);
    for (int i = 0; i < 20; i++) { CarInput ci = {0, 0, 0, 0}; carUpdate(&player, &world, &ci, DT); }
    carSetSpeed(&player, vs[iv]);
    float d0 = k->damage, jump = 0, dprev = d0; int phys = 0; unsigned r0 = k->reverts;
    for (int fr = 0; fr < 150; fr++) {
      CarInput ci = {0, 0, 0, 0}; ci.throttle = player.v < vs[iv] ? 1.f : 0.f; carUpdate(&player, &world, &ci, DT);
      float pp[3] = {player.x, player.y, player.z}, eye[3] = {player.x, player.y + 3, player.z}, fw[3] = {sinf(h), 0, cosf(h)};
      trafficUpdate(&T, &world, &player, 1, pp, eye, fw, DT);
      if (tc->mode == TRM_PHYS) phys = 1;
      if (getenv("TRACE") && n == atoi(getenv("TRACE")) && s == atoi(getenv("TS")) && iv == atoi(getenv("TV")) && k->damage != dprev) printf("  fr=%d dmg=%.3f (+%.3f) mode=%d v=%.1f pv=%.1f hitSpeed=%.1f lastHit=%.1f age=%.2f\n", fr, k->damage, k->damage - dprev, tc->mode, hypotf(k->vel[0], k->vel[2]), player.v, k->hitSpeed, k->lastHit, k->hitEpAge);
      if (k->damage - dprev > jump) jump = k->damage - dprev; dprev = k->damage;
    }
    if (!phys) continue;
    printf("%d\t%d\t%s\t%.0f\t%.2f\t%d\t%u\t%.2f\n", drv, (int)k->p.hitPoints, sides[s], vs[iv], k->damage - d0, k->destroyed, k->reverts - r0, jump);
    if (k->damage - d0 > worst) { worst = k->damage - d0; worstN = drv; }
  }
  fprintf(stderr, "макс. урон за удар %.2f (машина %d)\n", worst, worstN);
  return 0;
}
