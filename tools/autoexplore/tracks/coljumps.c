// Зоны прыжка и точки подбрасывания уровня (блок JMP1 в COL1): имя, центр, apex, объём.  coljumps level.shr
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "col.h"
static ColWorld w;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2; fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  unsigned char *d = aligned_alloc(16, (n + 15) & ~15); if (fread(d, 1, n, f) != (size_t)n) return 2; fclose(f);
  unsigned pvsOff = *(unsigned *)(d + 88), colOff = *(unsigned *)(d + 92), propOff = *(unsigned *)(d + 96); unsigned end = n;
  if (pvsOff && pvsOff < end && pvsOff > colOff) end = pvsOff; if (propOff && propOff < end && propOff > colOff) end = propOff;
  void *cm = aligned_alloc(16, ((end - colOff) + 15) & ~15); memcpy(cm, d + colOff, end - colOff); if (colInit(&w, cm, end - colOff)) return 1;
  for (unsigned i = 0; i < w.nzone; i++) { const ColZone *z = &w.zone[i]; printf("zone %u %.16s shape %u c %.2f %.2f %.2f h %.2f %.2f %.2f ax %.2f %.2f %.2f ay %.2f %.2f %.2f az %.2f %.2f %.2f\n", i, z->name, z->shape, z->c[0], z->c[1], z->c[2], z->h[0], z->h[1], z->h[2], z->ax[0], z->ax[1], z->ax[2], z->ay[0], z->ay[1], z->ay[2], z->az[0], z->az[1], z->az[2]); }
  for (unsigned i = 0; i < w.npad; i++) { const ColPad *z = &w.pad[i]; printf("pad %u %.16s shape %u c %.2f %.2f %.2f h %.2f %.2f %.2f apex %.2f %.2f %.2f\n", i, z->name, z->shape, z->c[0], z->c[1], z->c[2], z->h[0], z->h[1], z->h[2], z->apex[0], z->apex[1], z->apex[2]); }
  return 0;
}
