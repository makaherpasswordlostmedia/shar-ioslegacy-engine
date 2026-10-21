// №465 гейт стоп-сигналов трафика и машин миссий: в настоящем пакете у моделей есть куски-блики (owner 3); trafficDrawModel отдаёт их рисовке только когда горят
// (brkLit у тормозящей, v < 0 у заднего хода), у стоящей без торможения, разбитой и в дальней версии — нет. -DTRF_BRAKELIGHT_OLD=1 — красный контроль (ничего не горит)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "traffic.h"
static int nBrake, nRev, nOther;
static void fn(void *u, const TrPiece *p, const void *verts, const float m[16]) { (void)u; (void)verts; (void)m; if (p->owner == 3) { if (((p->flags >> 8) & 3) == 0) nBrake++; else nRev++; } else nOther++; }
int main(int argc, char **argv) {
  const char *trf = argc > 1 ? argv[1] : "build/traffic.shr";
  FILE *g = fopen(trf, "rb"); if (!g) { printf("no %s\n", trf); return 2; }
  fseek(g, 0, SEEK_END); unsigned size = (unsigned)ftell(g); fseek(g, 0, SEEK_SET);
  unsigned char *buf = aligned_alloc(64, (size + 63) & ~63u); if (fread(buf, 1, size, g) != size) return 2; fclose(g);
  static Traffic T; int r = trafficInitMem(&T, buf, size, 0); if (r) { printf("FAIL load %d\n", r); return 1; }
  int models = 0, withFlares = 0, bad = 0;
  for (unsigned mi = 0; mi < T.hd->nModel; mi++) {
    const TrModel *M = &T.model[mi]; int nf = 0, nb = 0;
    for (unsigned i = M->firstPiece; i < (unsigned)M->firstPiece + M->nPiece; i++) if (T.piece[i].owner == 3) { nf++; if (((T.piece[i].flags >> 8) & 3) == 0) nb++; }
    models++;
    Car k; memset(&k, 0, sizeof k); k.x = 0; k.y = 1; k.z = 0;
    nBrake = nRev = nOther = 0; k.brkLit = 0.f; k.v = 5.f; trafficDrawModel(M, T.piece, T.vert, &k, 0.f, 0, fn, 0, 0); int off = nBrake;
    nBrake = nRev = nOther = 0; k.brkLit = 1.f; trafficDrawModel(M, T.piece, T.vert, &k, 0.f, 0, fn, 0, 0); int on = nBrake, onRev = nRev;
    nBrake = nRev = nOther = 0; k.brkLit = 0.f; k.v = -2.f; trafficDrawModel(M, T.piece, T.vert, &k, 0.f, 0, fn, 0, 0); int rev = nRev;
    nBrake = nRev = nOther = 0; k.brkLit = 1.f; k.v = 5.f; trafficDrawModel(M, T.piece, T.vert, &k, 0.f, 1, fn, 0, 0); int lod = nBrake;   // дальняя версия: без бликов
    if (nf) withFlares++;
    if (off != 0 || onRev != 0 || lod != 0 || (nf && (on != nb || on == 0 || rev == 0))) { bad++; printf("  FAIL модель %.16s: бликов %d (стоп %d) горит %d погашена %d задний ход %d lod %d\n", M->name, nf, nb, on, off, rev, lod); }
  }
  printf("моделей %d, с бликами %d, нарушений %d\n", models, withFlares, bad);
  if (withFlares == 0) { printf("FAIL: в пакете нет бликов\n"); return 1; }
  return bad ? 1 : 0;
}
