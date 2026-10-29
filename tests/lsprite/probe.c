// Разведка №599: какие билборды SPR1 уровня «постоянный свет» (неподвижны, без покадровой анимации, без состояния/мигания).
// Только на хост-коде игры (tools/bots/world.c + viewer/stateprops.c), без экрана.  probe LEVEL.shr HOMER.shr
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"

int main(int argc, char **argv) {
  if (argc < 3 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "usage: probe level.shr homer.shr\n"); return 2; }
  static BotWorld w; if (bwNew(&w)) return 2;
  StateProps *sp = &w.sp; if (!w.haveSP) { printf("нет SPR1\n"); return 1; }
  for (int f = 0; f < 30; f++) spUpdate(sp, bwCol(), NULL, NULL, BW_DT);
  unsigned nB = 0, nAnim = 0, nPvis = 0, nSub = 0, nAdd = 0, nNorm = 0, nStateDep = 0, nMode[4] = {0}, nStatic = 0, nInst = 0;
  float wmax = 0;
  for (unsigned i = 0; i < sp->ninst; i++) {
    const SpType *T = &sp->type[sp->inst[i].type]; if (!T->nBill) continue; nInst++;
    spPose(sp, i);
    for (unsigned b = 0; b < T->nBill; b++) {
      const SpBill *B = &sp->bill[T->firstBill + b]; nB++;
      unsigned gi = T->firstBill + b; int anim = 0;
      if (sp->bqgIdx) { unsigned n = sp->bqgIdx[2 * gi + 1]; if (n > 1) anim = 1; }
      int pvis = (B->flags & SP_BILL_PVIS) != 0, blm = (B->flags >> 8) & 0xFF;
      nAnim += anim; nPvis += pvis; nMode[B->mode & 3]++;
      if (blm == 2) nAdd++; else if (blm == 3) nSub++; else nNorm++;
      float v[12]; uint32_t col, fl; int tex;
      int on = spBillQuad(sp, i, b, sp->run[i].x + 20.f, sp->run[i].y + 3.f, sp->run[i].z + 20.f, v, &col, &tex, &fl) && (col >> 24);
      if (!on) nStateDep++;
      if (!anim && !pvis && blm == 2 && on) { nStatic++; if (B->w > wmax) wmax = B->w; }
    }
  }
  printf("экз с билбордами %u, билбордов %u: сложение %u, вычитание(тень) %u, обычные %u; мода NOAX %u AAX %u YAX %u LYAX %u; анимация BQG %u, PVIS %u; не видны в состоянии 0: %u; ПОСТОЯННЫХ (сложение, без анимации и PVIS, видны) %u, макс ширина %.1f\n",
         nInst, nB, nAdd, nSub, nNorm, nMode[0], nMode[1], nMode[2], nMode[3], nAnim, nPvis, nStateDep, nStatic, wmax);
  return 0;
}
