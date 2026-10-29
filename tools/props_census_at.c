// Пропы и стейтпропы вокруг точки: tools/props_census_at.c LEVEL.shr x z [R 8] — тип, центр, полуразмеры коробки, масса, спит ли. Для разбора «машина стоит в чистом поле».
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "col.h"
#include "props.h"
#include "stateprops.h"
unsigned homerSolidFrame = 0;
static ColWorld W; static Props P; static StateProps S;
int main(int argc, char **argv) {
  if (argc < 4) return 2;
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *d = malloc((size + 15) & ~15); if (fread(d, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(d + 92), po = *(unsigned *)(d + 96), pv = *(unsigned *)(d + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&W, d + co, ce - co) || propsInit(&P, d + po, *(unsigned *)(d + po + 40))) return 3;
  if (P.spr) spInit(&S, P.spr, P.sprSize);
  float px = atof(argv[2]), pz = atof(argv[3]), R = argc > 4 ? atof(argv[4]) : 8.f; int n = 0;
  for (unsigned i = 0; i < P.ninst; i++) { const PropState *s = &P.st[i]; float dd = hypotf(s->x - px, s->z - pz); if (dd > R) continue;
    const PropType *t = &P.types[P.def[i].type]; printf("проп %u тип %u c(%.1f %.1f %.1f) полуразмеры(%.2f %.2f %.2f) масса %.1f радиус %.2f спит %d скрыт %d расстояние %.1f\n", i, P.def[i].type, s->x, s->y, s->z, s->hx, s->hy, s->hz, t->mass, t->radius, s->asleep, s->hidden, dd); n++; }
  for (unsigned i = 0; i < S.ninst; i++) { const SpRun *r = &S.run[i]; float dd = hypotf(r->x - px, r->z - pz); if (dd > R) continue;
    printf("стейтпроп %u тип %u c(%.1f %.1f %.1f) жив %d colOn %d расстояние %.1f\n", i, S.inst[i].type, r->x, r->y, r->z, r->alive, r->colOn, dd); n++; }
  printf("итого: %d\n", n); return 0;
}
