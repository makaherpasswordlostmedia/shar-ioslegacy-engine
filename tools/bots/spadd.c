// spadd — какие стейтпропы уровня с аддитивными кусками, билбордами или маской видимости (кандидаты на мигание №521 на АЭС)
#include <stdio.h>
#include <stdlib.h>
#include "world.h"
#define F_ADDITIVE (1 << 24)
static BotWorld W;
int main(int argc, char **argv) {
  if (argc < 4 || bwData(argv[1], argv[2], argv[3])) return 2;
  bwNew(&W); if (!W.haveSP) { printf("нет стейтпропов\n"); return 0; }
  for (unsigned t = 0; t < W.sp.ntype; t++) {
    const SpType *T = &W.sp.type[t]; int add = 0, blend = 0;
    for (unsigned k = 0; k < T->nPiece; k++) { unsigned fl = (unsigned)W.sp.piece[T->firstPiece + k].flags; add += (fl & F_ADDITIVE) != 0; blend += (fl & 2) != 0; }
    if (!add && !T->nBill && !T->pvisMask && !blend) continue;
    unsigned n = 0; float cx = 0, cz = 0, y = 0; for (unsigned i = 0; i < W.sp.ninst; i++) if (W.sp.inst[i].type == t) { n++; cx += W.sp.inst[i].x; cz += W.sp.inst[i].z; y += W.sp.inst[i].y; }
    printf("тип %u: кусков %u (аддитивных %d, полупрозрачных %d), билбордов %u, маска видимости %08x, кадров %u, экземпляров %u, центр %.0f %.0f %.0f\n", t, T->nPiece, add, blend, T->nBill, T->pvisMask, T->frames & 0xffff, n, n ? cx / n : 0, n ? y / n : 0, n ? cz / n : 0);
  }
  return 0;
}
