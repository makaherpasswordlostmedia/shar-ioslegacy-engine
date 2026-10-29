// Ядро запекания пропов (B1, propbake.h): какие экземпляры в покое годны для листа и какие у них куски/матрицы. Без зависимостей от PSP и от main_state.h — хост-тест
// tests/propbake/host.c подключает этот файл и сверяет с прямой копией прежнего цикла main_loop.h.
#ifndef PROPBAKE_CORE_H
#define PROPBAKE_CORE_H
#include <string.h>
#include "props.h"
#include "stateprops.h"
#ifndef F_ADDITIVE
#define F_ADDITIVE (1 << 24)
#endif
typedef struct { int tex, flags, ni; const void *v; const unsigned short *idx; float m[16]; } PbPiece;
typedef struct { unsigned id; float c[3], r; unsigned char hide, hasTr, nbig; float big[1][4], bb[1][6]; } PbMem;   // big: до двух крупных кусков (центр xyz, размер), BIG_CUT: клетка рисуется прежним путём, пока глаз ближе размера   // hasTr: у экземпляра есть прозрачные/аддитивные куски — они остаются за прежним путём
typedef int (*PbOkFn)(const PbPiece *);
typedef struct { float v[8]; unsigned char b[3]; } PbSig;   // b[2] — №975: угол падения столба стейтпропа (шарнир меняет поворот вокруг горизонтальной оси)
static inline void pbSigProp(const PropState *st, PbSig *g) {
  memset(g, 0, sizeof *g); g->v[0] = st->x; g->v[1] = st->y; g->v[2] = st->z; g->v[3] = st->q[0]; g->v[4] = st->q[1]; g->v[5] = st->q[2]; g->v[6] = st->q[3]; g->b[0] = (unsigned char)st->asleep; g->b[1] = (unsigned char)st->hidden;
}
static inline void pbSigSp(const SpRun *r, PbSig *g) {
  memset(g, 0, sizeof *g); g->v[0] = r->x; g->v[1] = r->y; g->v[2] = r->z; g->v[3] = r->poseF; g->v[4] = r->R[0]; g->v[5] = r->R[2]; g->v[6] = r->R[6]; g->v[7] = r->R[8]; g->b[0] = r->state; g->b[1] = r->alive; g->b[2] = (unsigned char)(r->fall ? 1 + (int)(r->fallTh * 40.f) : 0);
}
// n >= 0: НЕПРОЗРАЧНЫХ кусков для листа (0 — рисовать нечего), -1 — не запекать. Прозрачные и аддитивные куски в out не попадают (mm->hasTr = 1: их рисует прежний путь).
// mm: центр, радиус, «прячется у самого глаза» (правило №502: проп r<=1.5, стейтпроп r<=2.5)
static int pbCollectProp(const Props *P, unsigned i, PbPiece *out, int max, PbMem *mm, PbOkFn ok) {
  int n = 0; memset(mm, 0, sizeof *mm); mm->id = i;
  const PropState *st = &P->st[i]; const PropType *ty = &P->types[P->def[i].type];
  mm->c[0] = st->x; mm->c[1] = st->y; mm->c[2] = st->z; mm->r = ty->radius; mm->hide = ty->radius <= 1.5f;
  if (st->hidden) return 0;
  if (!st->asleep) return -1;
  for (unsigned k = 0; k < ty->nPiece; k++) {
    const PropPiece *pp = &P->pieces[ty->firstPiece + k]; if (pp->ni <= 0) continue;
    if (pp->flags & (2 | F_ADDITIVE)) { mm->hasTr = 1; continue; }
    if (n >= max) return -1;
    PbPiece *o = &out[n]; memset(o, 0, sizeof *o);
    o->tex = pp->tex; o->flags = pp->flags; o->ni = pp->ni; o->v = (const char *)P->vertBase + pp->vOff; o->idx = (const unsigned short *)((const char *)P->idxBase + pp->iOff);
    propPieceMatrix(st, pp->ox, pp->oy, pp->oz, pp->sc, o->m);
    if (ok && !ok(o)) return -1;
    n++;
  }
  return n;
}
#ifndef PB_SP_IDLE_OLD
#define PB_SP_IDLE_OLD 0
#endif
static int pbCollectSp(StateProps *S, unsigned i, PbPiece *out, int max, PbMem *mm, PbOkFn ok) {
  int n = 0; memset(mm, 0, sizeof *mm); mm->id = i;
  const SpType *T = &S->type[S->inst[i].type]; SpRun *r = &S->run[i];
  { float c[3], rr; spBounds(S, i, c, &rr); mm->c[0] = c[0]; mm->c[1] = c[1]; mm->c[2] = c[2]; mm->r = rr; mm->hide = rr <= 2.5f; }
  if (T->kind != 0) return -1;
  if (!r->alive) return 0;
  if (!spDrawable(S, i, 0.f, 0.f, 1e18f)) return 0;
  { const SpState *St = &S->state[T->firstState + r->state];
    // №?? (разбор тура 12): стейтпропы с анимацией (дверь, вывеска, ворота), стоящие без движения, раньше не запекались вовсе (L5: 1 из 304) — правило «поза не может меняться» отсекало
    // и тех, у кого поза просто не меняется сейчас. Сюда попадают только экземпляры, у которых подпись не менялась PB_STILL кадров (propbake.h pbFrameSet), любое движение снимает запекание.
    // PB_SP_IDLE_OLD=1 — прежнее правило
#if PB_SP_IDLE_OLD
    if (!(St->poseMode == 0 || St->poseMin == St->poseMax || (T->frames & 0xFFFFu) <= 1)) return -1;
#endif
  }
  spPose(S, i); if (!r->poseValid && T->nJoint) return -1;
  for (unsigned k = 0; k < T->nPiece; k++) {
    if (!spPieceOn(S, i, k)) continue;
    const SpPiece *pp = &S->piece[T->firstPiece + k]; if (!pp->ni) continue;
    if (pp->flags & (2 | F_ADDITIVE)) { mm->hasTr = 1; continue; }
    if (n >= max) return -1;
    PbPiece *o = &out[n]; memset(o, 0, sizeof *o);
    o->tex = pp->tex; o->flags = pp->flags & (0xFF | F_ADDITIVE); o->ni = (int)pp->ni; o->v = (const char *)S->vertBase + pp->vOff; o->idx = (const unsigned short *)((const char *)S->idxBase + pp->iOff);
    spPieceMatrix(S, i, k, o->m);
    if (ok && !ok(o)) return -1;
    n++;
  }
  return n;
}
#endif
