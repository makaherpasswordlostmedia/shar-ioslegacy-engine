// Правка 413 (хвост): следов шин под парящими машинами нет — Мак, тот же car.c/col.c/skid.c, что на PSP (SKID_HOST), уровень
// build/level.shr (следы у порта сейчас только на уровне 1, слово Роба 03.10 — поэтому замер на Маке, а не в эмуляторе на L7).
// SLES_518.97: байт +657 машины ставится по имени для hbike_v, frink_v, ship, witchcar, mono_v (0x28d8ec…0x28dd94); функция колёс
// следа 0x288378 при нём выходит (0x2884d8). Резкий тормоз с 15 м/с на ровном месте у спавна L1, как tests/skid/host.c A:
// famil_v, honor_v, rocke_v (байт +658, колёса в кузове — следы есть) -> следы есть; пять парящих -> 0 квадов.
// Красный: -DSKID_HOVER_OLD=1 (прежнее) — у парящих следы есть, обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "car.h"
#include "skid.h"
static ColWorld W;
#define DT (1 / 60.f)
static int quads(void) { int n = 0; float p[4][3]; unsigned char a[4]; for (int i = 0; i < SKID_QUADS; i++) n += skidQuadAt(i, p, a); return n; }
static int brake(const char *name) {
  Car c; float g; if (!colGround(&W, 200.f, 172.f, 50, -50, &g, 0)) exit(2);
  skidClear(1); carInit(&c, NULL, &W, 200.f, g, 172.f, 1.5708f);
  for (int k = 0; k < 30; k++) { CarInput in = {0, 0, 0, 0}; carUpdate(&c, &W, &in, DT); }
  strncpy(c.p.name, name, sizeof c.p.name - 1); c.p.name[sizeof c.p.name - 1] = 0;
  carSetSpeed(&c, 15.f);
  for (int k = 0; k < 600; k++) { CarInput in = {0, k < 5 ? 0.f : 1.f, 0, 0}; carUpdate(&c, &W, &in, DT); skidCar(0, &c, &in, &W); }
  return quads();
}
int main(int argc, char **argv) {
  if (argc < 2) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)n;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co)) return 2;
  const char *wheel[] = {"famil_v", "honor_v", "rocke_v"}, *hover[] = {"hbike_v", "frink_v", "ship", "witchcar", "mono_v"}; int fails = 0;
  for (int i = 0; i < 3; i++) { int q = brake(wheel[i]); printf("%s %s: квадов следа %d (нужно > 0)\n", q > 0 ? "ok  " : "FAIL", wheel[i], q); fails += q <= 0; }
  for (int i = 0; i < 5; i++) { int q = brake(hover[i]); printf("%s %s: квадов следа %d (нужно 0)\n", q == 0 ? "ok  " : "FAIL", hover[i], q); fails += q != 0; }
  return fails ? 1 : 0;
}
