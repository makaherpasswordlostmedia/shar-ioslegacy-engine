// Хост-сверка запекания пропов (viewer/propbake_core.h, B1): на каждом уровне 1–7 в покое (начальное состояние) набор кусков и матрицы запекаемых экземпляров должны совпасть
// бит в бит с прямой копией прежнего цикла main_loop.h (пропы: propPieceMatrix; стейтпропы: spPose + spPieceOn + spPieceMatrix, маска флагов), плюс доля запекаемого и причины отказа;
// подпись экземпляра обязана меняться при ударе (spEnter в другое состояние).
//   cc -std=c99 -O2 -I viewer tests/propbake/host.c viewer/col.c viewer/car.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o build/propbake_host && build/propbake_host level.shr ...
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include "propbake_core.h"
unsigned homerSolidFrame;   // заглушка: props.c ждёт счётчик кадра Гомера
int main(int argc, char **argv) {
  int bad = 0;
  for (int a = 1; a < argc; a++) {
    FILE *f = fopen(argv[a], "rb"); if (!f) { printf("%s: нет файла\n", argv[a]); bad++; continue; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); unsigned char *file = malloc(sz); if (fread(file, 1, sz, f) != (size_t)sz) return 2; fclose(f);
    unsigned po = *(unsigned *)(file + 96); static Props P; static StateProps S; memset(&P, 0, sizeof P); memset(&S, 0, sizeof S);
    if (!po || propsInit(&P, file + po, *(unsigned *)(file + po + 40)) || spInit(&S, P.spr, P.sprSize)) { printf("%s: нет PRP2\n", argv[a]); bad++; continue; }
    // пропы
    unsigned pe = 0, pp = 0, pall = 0, ppall = 0, pt = 0, mism = 0, hidden = 0, popq = 0, ptrp = 0;
    for (unsigned i = 0; i < P.ninst; i++) {
      PbPiece out[64]; PbMem mm; int n = pbCollectProp(&P, i, out, 64, &mm, 0);
      const PropState *st = &P.st[i]; const PropType *ty = &P.types[P.def[i].type]; pall++; for (unsigned k = 0; k < ty->nPiece; k++) if (P.pieces[ty->firstPiece + k].ni > 0) ppall++;
      if (st->hidden) { hidden++; if (n != 0) mism++; continue; }
      int trans = 0, cnt = 0; PbPiece ref[64];
      for (unsigned k = 0; k < ty->nPiece; k++) { const PropPiece *p = &P.pieces[ty->firstPiece + k]; if (p->ni <= 0) continue;
        if (p->flags & (2 | F_ADDITIVE)) trans = 1;
        PbPiece *r = &ref[cnt++]; memset(r, 0, sizeof *r); r->tex = p->tex; r->flags = p->flags; r->ni = p->ni; r->v = (char *)P.vertBase + p->vOff; r->idx = (unsigned short *)((char *)P.idxBase + p->iOff);
        propPieceMatrix(st, p->ox, p->oy, p->oz, p->sc, r->m); }
      int nopq = 0; PbPiece refo[64]; for (int k = 0; k < cnt; k++) { if (ref[k].flags & (2 | F_ADDITIVE)) ptrp++; else refo[nopq++] = ref[k]; }
      if (trans) pt++;
      if (n != nopq || (mm.hasTr != (unsigned char)trans)) { mism++; continue; }
      pe++; pp += (unsigned)nopq; popq += trans ? (unsigned)nopq : 0; for (int k = 0; k < nopq; k++) if (memcmp(&out[k], &refo[k], sizeof out[k])) mism++;
    }
    // стейтпропы
    unsigned sOpqAnim = 0, sTrpAnim = 0, sOpqTrans = 0, sTrpTrans = 0, se = 0, sp = 0, sall = 0, spall = 0, kindn = 0, dead = 0, anim = 0, strans = 0, nopose = 0, smism = 0, sigok = 0, sigtry = 0;
    for (unsigned i = 0; i < S.ninst; i++) {
      const SpType *T = &S.type[S.inst[i].type]; sall++; if (T->kind == 0) spall += T->nPiece;
      PbPiece out[64]; PbMem mm; int n = pbCollectSp(&S, i, out, 64, &mm, 0);
      if (T->kind != 0) { kindn++; if (n != -1) smism++; continue; }
      if (!S.run[i].alive) { dead++; continue; }
      if (n == -1) { const SpState *St = &S.state[T->firstState + S.run[i].state];
        int isanim = !(St->poseMode == 0 || St->poseMin == St->poseMax || (T->frames & 0xFFFFu) <= 1); int tr = 0; for (unsigned k = 0; k < T->nPiece; k++) if (spPieceOn(&S, i, k) && (S.piece[T->firstPiece + k].flags & (2 | F_ADDITIVE))) tr = 1;
        for (unsigned k = 0; k < T->nPiece; k++) { if (!spPieceOn(&S, i, k) || !S.piece[T->firstPiece + k].ni) continue; int tp = (S.piece[T->firstPiece + k].flags & (2 | F_ADDITIVE)) != 0; if (isanim) { if (tp) sTrpAnim++; else sOpqAnim++; } else { if (tp) sTrpTrans++; else sOpqTrans++; } }
        if (isanim) anim++; else { if (tr) strans++; else nopose++; }
        continue; }
      // прямая копия прежнего цикла
      SpRun *r = &S.run[i]; spPose(&S, i); int cnt = 0, sHasTr = 0; PbPiece ref[64];
      for (unsigned k = 0; k < T->nPiece; k++) { if (!spPieceOn(&S, i, k)) continue; const SpPiece *p = &S.piece[T->firstPiece + k]; if (!p->ni) continue;
        if (p->flags & (2 | F_ADDITIVE)) { sHasTr = 1; continue; }
        PbPiece *q = &ref[cnt++]; memset(q, 0, sizeof *q); q->tex = p->tex; q->flags = p->flags & (0xFF | F_ADDITIVE); q->ni = (int)p->ni; q->v = (char *)S.vertBase + p->vOff; q->idx = (unsigned short *)((char *)S.idxBase + p->iOff);
        spPieceMatrix(&S, i, k, q->m); }
      (void)r; if (n != cnt || mm.hasTr != (unsigned char)sHasTr) { smism++; continue; }
      se++; sp += (unsigned)cnt; for (int k = 0; k < cnt; k++) if (memcmp(&out[k], &ref[k], sizeof out[k])) smism++;
      // подпись меняется при ударе: переводим экземпляр в другое состояние
      if (T->nState > 1) { PbSig g0, g1; pbSigSp(&S.run[i], &g0); spEnter(&S, i, 1 % T->nState ? 1 : 0); pbSigSp(&S.run[i], &g1); sigtry++; if (memcmp(&g0, &g1, sizeof g0)) sigok++; spEnter(&S, i, 0); }
    }
    printf("   [куски вне запекания: пропы: непрозрачных в экземплярах с прозрачными %u, прозрачных %u; стейтпропы: анимированные экземпляры: непрозрачных %u прозрачных %u, неанимированные с прозрачными: непрозрачных %u прозрачных %u]\n", popq, ptrp, sOpqAnim, sTrpAnim, sOpqTrans, sTrpTrans);
    printf("%s: props %u (спрятано %u): запекаемых %u, кусков %u из %u; с прозрачными/аддитивными кусками %u (прежним путём); расхождений %u | стейтпропы %u: запекаемых %u, кусков %u из %u (вид kind0), не kind0 %u, убраны %u, анимация %u, прозрачные %u, прочее %u; расхождений %u; подпись меняется при ударе %u из %u\n",
           argv[a], pall, hidden, pe, pp, ppall, pt, mism, sall, se, sp, spall, kindn, dead, anim, strans, nopose, smism, sigok, sigtry);
    if (mism || smism || sigok != sigtry) bad++;
    free(file);
  }
  printf(bad ? "FAIL\n" : "OK\n"); return bad ? 1 : 0;
}
