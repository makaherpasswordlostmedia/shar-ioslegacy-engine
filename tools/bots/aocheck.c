// Гейт правки 116 (30.09): объекты ANM1 в мире ботов шагают тем же viewer/animobj.c, что EBOOT, и снимок мира их возвращает.
// Каждый объект с действием по △ (PlayAnim / ToggleOnOff) и живым объёмом: машина рядом, △ объекту, 1 с — сохранить, 3 с (верх
// последнего объёма и отпечаток мира каждый кадр), загрузить — верх сразу после загрузки = сохранённому, те же 3 с = те же байты;
// клип за 4 с сдвинул или повернул объём (объект шагает). Красный: сборка -DBW_BREAK_AO_LOAD=1 (загрузка без объёмов), BW_NO_AO=1 (стоят).
//   aocheck LEVEL HOMER -> строки по объектам, RESULT: OK / FAIL
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"
static BotWorld W;
#ifdef BW_HAVE_AO
static float top(const AoVol *V) {   // верх живого объёма (центр + проекции полуосей на вертикаль)
  const ColWorld *cw = bwCol();
  if (V->kind == 0) { const ColBox *b = &cw->box[V->col]; return b->c[1] + fabsf(b->ax[1]) * b->h[0] + fabsf(b->ay[1]) * b->h[1] + fabsf(b->az[1]) * b->h[2]; }
  const ColCyl *c = &cw->cyl[V->col]; return c->c[1] + fabsf(c->axis[1]) * c->halfLen;
}
static float moved(const AoVol *V, const float *c0, const float *a0) {   // сдвиг центра и поворот оси объёма от начального (м)
  const ColWorld *cw = bwCol(); const float *c = V->kind == 0 ? cw->box[V->col].c : cw->cyl[V->col].c, *a = V->kind == 0 ? cw->box[V->col].ax : cw->cyl[V->col].axis;
  return fmaxf(hypotf(hypotf(c[0] - c0[0], c[1] - c0[1]), c[2] - c0[2]), hypotf(hypotf(a[0] - a0[0], a[1] - a0[1]), a[2] - a0[2]));
}
#endif
int main(int argc, char **argv) {
  if (argc < 3 || bwData(argv[1], argv[2], NULL)) { fprintf(stderr, "usage: aocheck LEVEL HOMER\n"); return 2; }
#ifndef BW_HAVE_AO
  printf("RESULT: FAIL (нет viewer/animobj.h)\n"); return 1;
#else
  bwNew(&W); if (!W.haveAo) { printf("объекты ANM1 не шагают (BW_NO_AO или нет таблицы)\nRESULT: FAIL\n"); return 1; }
  BotSnap s; bwSaveAlloc(&W, &s); int bad = 0, n = 0;
  for (unsigned k = 0; k < W.ao.nobj; k++) {
    const AoObj *o = &W.ao.obj[k]; if ((o->action != AO_PLAYANIM && o->action != AO_TOGGLE) || !o->nVol) continue;
    bwFree(&W); bwNew(&W);
    const SpRun *r = &W.sp.run[o->firstInst]; bwPlace(&W, r->x + 6.f, r->y + 1.f, r->z, 0.f);   // машина в 6 м (объёмы шагают только рядом)
    for (int i = 0; i < 30; i++) bwStep(&W, 0, 0, 0);
    W.ao.want = (int)k; aoStep(&W.ao, &W.sp, (ColWorld *)bwCol(), W.car.x, W.car.y, W.car.z, 1, 1, 0.f);   // △ объекту
    const AoVol *V = &W.ao.vol[o->firstVol + o->nVol - 1]; float t0 = top(V), c0[3], a0[3];
    memcpy(c0, V->kind == 0 ? bwCol()->box[V->col].c : bwCol()->cyl[V->col].c, 12); memcpy(a0, V->kind == 0 ? bwCol()->box[V->col].ax : bwCol()->cyl[V->col].axis, 12);
    for (int i = 0; i < 60; i++) bwStep(&W, 0, 0, 0);
    bwSave(&W, &s); float tS = top(V), mv = 0.f; uint64_t h[180];
    for (int i = 0; i < 180; i++) { bwStep(&W, 0, 0, 0); h[i] = bwHash(&W); mv = fmaxf(mv, moved(V, c0, a0)); }
    bwLoad(&W, &s); float tL = top(V); int diff = -1;
    for (int i = 0; i < 180; i++) { bwStep(&W, 0, 0, 0); if (diff < 0 && bwHash(&W) != h[i]) diff = i; }
    int ok = fabsf(tL - tS) < 1e-4f && diff < 0 && mv > .05f; bad |= !ok; n++;
    printf("объект %u (действие %d): верх %.2f, сдвиг/поворот за 4 с %.2f; после загрузки %.3f (сохранено %.3f); повтор 3 с %s — %s\n", k, o->action, t0, mv, tL, tS,
           diff < 0 ? "побайтно" : "РАЗОШЁЛСЯ", ok ? "ок" : "FAIL");
  }
  printf("RESULT: %s (%d объектов)\n", !bad && n ? "OK" : "FAIL", n); return !bad && n ? 0 : 1;
#endif
}
