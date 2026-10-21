// Отлёт машины трафика от удара машиной игрока против PS2 (аудит 09.10, п. 14; карточка knowledge/facts/ps2-traffic-hit.yaml).
// Записи близнеца build/ps2ref/answers/tw_v14_hit20, tw_v14_hit35 (рецепты tools/twins/recipes/tw_v14_hit*.json): на кадре 400
// центр масс машины Гомера ставится у минивэна трафика (+0,763/+1,263 м по x, −7,643 по z, оси PS2), скорость вдоль носа
// (курс −17,2°) 20 и 35 м/с держится 4 кадра, дальше настоящее столкновение игры. Минивэн едет по улице −x ~3,3 м/с.
// PS2: минивэн смещён на 7,7 м (20 м/с) и 23,0 м с разворотом (35 м/с), всё — к концу записи (~22 с).
// Порт: тот же мир, параметры minivana из traffic.shr (как в игре), удар carHitCar, после удара — carUpdate с ручником
// (traffic.c physStep), 50 Гц. Печатает смещение минивэна и машины игрока; код выхода 0, если смещение минивэна в ±25 % PS2.
// Состояние 09.10: FAIL (2,6 и 7,4 м против 7,7 и 23,0), в матрицу не включён — разбор и что не хватает (В106) в
// docs/handoff/ФИЗИКА_СВЕРКА_PS2_2026-10-09.md, шаг 5.
//   cc -std=c11 -O2 -DSKIN_HOST -I viewer tests/cars/knock_ps2.c viewer/car.c viewer/col.c viewer/traffic.c viewer/homer.c viewer/skin.c -lm
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <math.h>
#include "car.h"
#include "traffic.h"
static ColWorld W; static Traffic T;
static float run(const CarParams *vp, float dxPs2, float vx, float vz, float *playerMove, float *vanTurn) {
  // минивэн: PS2 (205,405; −156,06) → оси движка (205,405; 156,06), едет −x
  float vxv = 205.405f, vzv = 156.06f, g; colGround(&W, vxv, vzv, 10.f, -10.f, &g, 0);
  Car van; carInit(&van, vp, &W, vxv, g, vzv, -1.5707963f);
  float px = vxv + dxPs2, pz = vzv + 7.643f, gp; colGround(&W, px, pz, 10.f, -10.f, &gp, 0);
  Car pl; carInit(&pl, NULL, &W, px, gp, pz, atan2f(vx, -vz));
  for (int k = 0; k < 10; k++) { CarInput n0 = {0}; carUpdate(&pl, &W, &n0, 1 / 50.f); }
  pl.x = px; pl.z = pz;
  float x0 = van.x, z0 = van.z, h0 = van.h, plx0 = 0, plz0 = 0; int hit = 0;
  for (int f = 0; f < 50 * 22; f++) {
    if (f < 4) { pl.vel[0] = vx; pl.vel[2] = -vz; }
    if (!hit) { van.vel[0] = -3.3f; van.vel[2] = 0.f; }
    CarInput none = {0, 0, 0, 0}, hb = {0, 0, 0, 1};
    carUpdate(&pl, &W, &none, 1 / 50.f); carUpdate(&van, &W, hit ? &hb : &none, 1 / 50.f);
    if (carHitCar(&pl, &van, &W) && !hit) { hit = 1; x0 = van.x; z0 = van.z; h0 = van.h; plx0 = pl.x; plz0 = pl.z; }
  }
  *playerMove = hypotf(pl.x - plx0, pl.z - plz0);
  float dh = remainderf(van.h - h0, 6.2831853f); *vanTurn = fabsf(dh) * 57.2958f;
  return hit ? hypotf(van.x - x0, van.z - z0) : -1.f;
}
int main(int argc, char **argv) {
  const char *lv = argc > 1 ? argv[1] : "build/level.shr", *tr = argc > 2 ? argv[2] : "build/traffic.shr";
  FILE *f = fopen(lv, "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  if (trafficLoad(&T, tr)) { printf("нет %s\n", tr); return 2; }
  int mi = -1; for (int i = 0; i < (int)T.hd->nModel; i++) if (!strncasecmp(T.model[i].name, "minivana", 8)) mi = i;
  if (mi < 0) { printf("нет minivana в traffic.shr\n"); return 2; }
  struct { const char *id; float dx, vx, vz, ps2; } c[2] = {{"hit20", .763f, -5.908f, 19.107f, 7.7f}, {"hit35", 1.263f, -10.339f, 33.438f, 23.0f}};
  int fails = 0;
  for (int i = 0; i < 2; i++) {
    float pm, turn, m = run(&T.params[mi], c[i].dx, c[i].vx, c[i].vz, &pm, &turn); int ok = m > 0 && fabsf(m - c[i].ps2) <= .25f * c[i].ps2; fails += !ok;
    printf("%s %s: минивэн смещён %.1f м (PS2 %.1f), развернулся на %.0f°, машина игрока после удара %.1f м\n", ok ? "ok  " : "FAIL", c[i].id, m, c[i].ps2, turn, pm);
  }
  printf("knock_ps2: %s\n", fails ? "FAIL" : "PASS"); return fails;
}
