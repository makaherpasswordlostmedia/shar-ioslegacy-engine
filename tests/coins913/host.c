// разбор L3/L5: шаг монет по сетке против прежнего полного обхода — состояние на одинаковых входах (Мак, только числа).
// Игрок идёт по случайной траектории по карте 700×700 м (600 монет мира для густоты подборов), иногда из точки выбрасывается 1–12 монет (пул); каждый шаг печатается хеш: кошелёк, пул целиком, монеты мира в 90 м от игрока (активность, сбор, место)
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "../../viewer/coins.h"
static unsigned rs = 777; static float rnd(void) { rs = rs * 1664525u + 1013904223u; return (rs >> 8) * (1.f / 16777216.f); }
static unsigned fnv(unsigned h, const void *p, size_t n) { const unsigned char *b = p; for (size_t i = 0; i < n; i++) h = (h ^ b[i]) * 16777619u; return h; }
int main(int argc, char **argv) {
  unsigned frames = argc > 1 ? (unsigned)atoi(argv[1]) : 6000;
  float pos[600 * 3]; for (int i = 0; i < 600; i++) { pos[i * 3] = rnd() * 700.f; pos[i * 3 + 1] = 2.f; pos[i * 3 + 2] = rnd() * 700.f; }
  Coins cs; if (coinsInit(&cs, pos, 600)) return 2;
  float px = 350.f, pz = 350.f, yaw = 0.f; unsigned bad = 0; unsigned long long sum = 0;
  for (unsigned f = 0; f < frames; f++) {
    if (!(f % 30)) yaw += (rnd() - .5f) * 1.5f;
    float sp = (f / 600) % 3 == 0 ? 9.f : (f / 600) % 3 == 1 ? 20.f : 0.f;   // ходьба, езда, стоянка
    px += cosf(yaw) * sp / 30.f; pz += sinf(yaw) * sp / 30.f; if (px < 0 || px > 700) yaw = 3.1416f - yaw; if (pz < 0 || pz > 700) yaw = -yaw;
    if (!(f % 400)) coinsDrop(&cs, 1 + (int)(rnd() * 12.f), px + 3.f, 2.f, pz, 1.5f);
    int e = coinsUpdate(&cs, px, 2.f, pz, (f / 600) % 3 == 1, 1.f / 30.f); (void)e;
    unsigned h = 2166136261u; h = fnv(h, &cs.collected, sizeof cs.collected);
    for (unsigned i = cs.nworld; i < cs.n; i++) { const Coin *c = &cs.c[i]; h = fnv(h, &c->active, 1); if (c->active) { h = fnv(h, &c->x, 12); h = fnv(h, &c->age, 4); h = fnv(h, &c->collecting, 1); } }
    for (unsigned i = 0; i < cs.nworld; i++) { const Coin *c = &cs.c[i]; float dx = c->x - px, dz = c->z - pz; if (dx * dx + dz * dz > 85.f * 85.f && !c->collecting) { h = fnv(h, &c->active, 1); continue; } h = fnv(h, &c->active, 1); h = fnv(h, &c->collecting, 1); h = fnv(h, &c->x, 12); }
    sum += h; printf("%u %08x\n", f, h);
  }
  (void)bad; (void)sum; coinsFree(&cs); return 0;
}
