// №368/377 (L6 «удар на трамплине отбрасывает задом вверх», «большие трамплины: сильный удар и ложный возврат»): рой заездов в зоны прыжка уровня. Для каждой зоны jumpzone*
// машина стартует с 16 курсов с расстояния 45 м (где есть земля и разгон по прямой доходит до зоны), на 15/25 м/с, газ держит скорость; 8 с. Аномалия «отброс»: после первого
// контакта (wallV > 1 или ступень) скорость ВДОЛЬ исходного курса < −2 м/с (отброшена назад) или vy > 9 м/с без зоны (подброс). «Возврат»: reverts/сброс позиции > 8 м за кадр.
// Сверка по уровням: L1 откалиброван близнецом (tests/jumps/twin.sh, 14 заездов PS2) — аномалий на нём столько, сколько допустим на остальных.
// cc -std=c11 -O2 -I viewer tools/cartest/ramp_swarm.c viewer/car.c viewer/col.c -lm ; ./a.out level.shr
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "car.h"
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); unsigned n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != n) return 2; fclose(f);
  unsigned co = *(unsigned *)(b + 92), po = *(unsigned *)(b + 96), pv = *(unsigned *)(b + 88), end = n; if (po > co && po < end) end = po; if (pv > co && pv < end) end = pv;
  ColWorld w; if (colInit(&w, b + co, end - co)) return 2;
  int falseRet = 0, bkTot = 0, nr = 0, back = 0, pop = 0, jumpfar = 0, zonesUsed = 0; printf("зона\tимя\tкурс°\tv\tмин_вдоль\tmax_vy\tскачок_м\n");
  for (unsigned zi = 0; zi < w.nzone; zi++) {
    const ColZone *Z = &w.zone[zi]; if (strncmp(Z->name, "jumpzone", 8) && 0) continue;
    int used = 0;
    for (int hd = 0; hd < 16; hd++) for (int iv = 0; iv < 2; iv++) {
      float a = hd * 6.2831853f / 16, dx = sinf(a), dz = cosf(a), vt = iv ? 25.f : 15.f;
      float sx = Z->c[0] - dx * 45.f, sz = Z->c[2] - dz * 45.f, g;
      if (!colGround(&w, sx, sz, Z->c[1] + 30, Z->c[1] - 30, &g, 0)) continue;
      Car c; carInit(&c, NULL, &w, sx, g, sz, a); for (int i = 0; i < 20; i++) carUpdate(&c, &w, &(CarInput){0}, 1.f / 60);
      if (hypotf(c.x - sx, c.z - sz) > 1.f) continue;
      carSetSpeed(&c, vt); float retY = 0, py = c.y, minAlong = 1e9, maxVy = 0, jump = 0, px = c.x, pz = c.z; int hit = 0, started = 0, bkup = 0; used = 1;
      for (int fr = 0; fr < 480; fr++) {
        CarInput in = {0}; in.throttle = c.v < vt ? 1.f : 0.f; carUpdate(&c, &w, &in, 1.f / 60);
        float al = c.vel[0] * dx + c.vel[2] * dz; float d = hypotf(c.x - Z->c[0], c.z - Z->c[2]);
        if (d < 25.f) started = 1;
        if (started && al < -2.f && c.vel[1] > 3.f) bkup++;
        if (started) { if (al < minAlong) minAlong = al; if (c.vel[1] > maxVy) maxVy = c.vel[1]; }
        float jp = hypotf(c.x - px, c.z - pz); if (started && jp > jump) jump = jp;
        if (getenv("TR") && zi == (unsigned)atoi(getenv("TR")) && hd == atoi(getenv("TH")) && iv == atoi(getenv("TV")) && (jp > 3.f || (fr % 15 == 0 && started))) printf("  fr=%d pos=(%.1f,%.2f,%.1f) v=%.1f vy=%.1f wheels=%d jump=%.1f rev=%d why=%d zdist=%.1f\n", fr, c.x, c.y, c.z, c.v, c.vel[1], c.wheels, jp, c.reverts, c.revWhy, d); if (jp > 8.f && !retY) retY = py; px = c.x; pz = c.z; py = c.y; (void)hit;
      }
      nr++; bkTot += bkup > 0; falseRet += (jump > 8.f && retY > Z->c[1] - 3.f); int bk = started && bkup > 0, pp = started && maxVy > 9.f, jf = jump > 8.f; back += bk; pop += pp; jumpfar += jf;
      if (bk || pp || jf) printf("%u\t%s\t%d\t%.0f\t%.1f\t%.1f\t%.1f (до возврата y=%.1f; зона y=%.1f)%s%s%s\n", zi, Z->name, hd * 22, vt, minAlong, maxVy, jump, retY, Z->c[1], bk ? " ОТБРОС" : "", pp ? " ПОДБРОС" : "", jf ? " ВОЗВРАТ" : "");
    }
    zonesUsed += used;
  }
  printf("задом-вверх (скорость назад > 2 м/с одновременно с подъёмом > 3 м/с): %d, ложных возвратов (скачок > 8 м не из ямы глубже 3 м): %d\nRESULT зон %d (с заездами %d), заездов %d, отброс назад %d, подброс %d, скачок >8 м %d\n", bkTot, falseRet, w.nzone, zonesUsed, nr, back, pop, jumpfar);
  return 0;
}
