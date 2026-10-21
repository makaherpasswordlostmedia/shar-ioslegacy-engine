// Прочность машины игрока против PS2 (аудит 09.10, п. 6): тот же бот, что у близнеца tools/twins/boom.py (запись PS2
// build/twins/o4/v199_boom/boom.tsv, 50 к/с): со старта L1 разгон газом до удара (скорость упала ниже 60 % от наибольшей),
// 40 кадров ждать, задний ход 130 кадров с рулём на исходный курс, 20 кадров стоять, снова. У PS2 famil_v (HitPoints 3,0) разбита
// 12-м ударом (кадр ~3356: дальше машина стоит, взрыв через 3 с), удары 13,9–20,4 м/с (вперёд в изгородь ~19–20, назад ~15).
// Порт: тот же мир (build/level.shr, столкновения col.c), тот же carUpdate, 50 Гц. Удар считается по приросту урона (вперёд и
// задом, как у бота PS2), не чаще раза в 10 кадров. Красный: -DCAR_WALL_DMG_OLD=1 (разбита 9-м ударом); -DCAR_REVERT_DMG_OLD=1 (удар с отменой подшага о твёрдую изгородь на цоколе L1 не давал урона: 14-й удар, ударов 22). Нужен L1 с твёрдой common_gens10Shape (Уровни, reissue2, sha 440b03b7).
//   cc -std=c11 -O2 -I viewer tests/cars/boom_ps2.c viewer/car.c viewer/col.c -lm -o boom_ps2 && ./boom_ps2 build/level.shr [--ps2 12]
// Код выхода 0, если машина разбита тем же по счёту ударом, что у PS2 (±1 удар — граница одной записи), иначе 1.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
static ColWorld W;
static float ang(float a) { while (a > 3.14159265f) a -= 6.2831853f; while (a < -3.14159265f) a += 6.2831853f; return a; }
int main(int argc, char **argv) {
  if (argc < 2) return 2; int ps2 = 12;
  for (int i = 2; i < argc; i++) if (!strcmp(argv[i], "--ps2") && i + 1 < argc) ps2 = atoi(argv[++i]);
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  // старт PS2 (state_l1_incar): начало модели (215,054; 4,051; −170,248), курс −17,2° → оси движка: z отзеркален, курс π − курс
  float x0 = 215.054f, z0 = 170.248f, h0 = 3.14159265f + 17.2f * 0.0174533f, g;
  if (!colGround(&W, x0, z0, 10.f, -10.f, &g, 0)) return 2;
  Car c; carInit(&c, NULL, &W, x0, g, z0, h0);
  enum { RUN, HIT, BACK, STOP } ph = RUN; int t0 = 0, hits = 0, deadHit = 0, nev = 0, lastEv = -100; float ev[64]; float vmax = 0.f, prevV = 0.f, hv[64];
  for (int fr = 0; fr < 7000 && !c.destroyed; fr++) {
    float v = hypotf(c.vel[0], c.vel[2]); CarInput in = {0, 0, 0, 0};
    if (fr >= 40) {
      if (ph == RUN) { in.throttle = 1.f; if (v > vmax) vmax = v;
        if (vmax > 6.f && v < .6f * vmax && fr - t0 > 30) { if (hits < 64) hv[hits] = prevV > vmax ? prevV : vmax; hits++; ph = HIT; t0 = fr; vmax = 0.f; }
        else if (fr - t0 > 400) { ph = BACK; t0 = fr; } }
      else if (ph == HIT) { if (fr - t0 > 40) { ph = BACK; t0 = fr; } }
      else if (ph == BACK) { float err = ang(h0 - c.h); in.brake = 1.f; in.steer = fmaxf(-1.f, fminf(1.f, err * 2.f));
        if (v > vmax) vmax = v;
        if (vmax > 6.f && v < .6f * vmax) { if (hits < 64) hv[hits] = vmax; hits++; vmax = 0.f; }   // удар задом (у PS2 — тоже «удар»)
        if (fr - t0 > 130) { ph = STOP; t0 = fr; vmax = 0.f; } }
      else if (ph == STOP) { if (fr - t0 > 20) { ph = RUN; t0 = fr; vmax = 0.f; } }
    }
    float d0 = c.damage; prevV = v; carUpdate(&c, &W, &in, 1 / 50.f);
    if (c.damage > d0 && fr - lastEv > 10) { if (nev < 64) ev[nev] = c.lastHit; nev++; lastEv = fr; }   // удар с уроном (вперёд и задом)
    if (c.destroyed) deadHit = nev;
  }
  printf("порт: ударов с уроном %d (разгонов с ударом %d), урон %.2f, разбита %s", nev, hits, c.damage, c.destroyed ? "да" : "нет");
  if (c.destroyed) printf(" (удар %d)", deadHit);
  printf("; скорость сближения:"); for (int i = 0; i < nev && i < 64; i++) printf(" %.1f", ev[i]); (void)hv;
  printf("\nPS2: разбита 12-м ударом (13,9–20,4 м/с)\n");
  int ok = c.destroyed && abs(deadHit - ps2) <= 1;
  printf("boom_ps2: %s\n", ok ? "PASS" : "FAIL"); return !ok;
}
