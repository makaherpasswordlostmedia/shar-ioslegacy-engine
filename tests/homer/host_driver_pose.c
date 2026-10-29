// B5 (ОПТИМИЗАЦИЯ_ПЛАН_ФИНАЛ): хост-проверка позы водителя через кадр (viewer/homer.c homerPose, DRIVER_POSE_OLD).
// Два Гомера на одном клипе: A — как в игре (полная поза через кадр, промежуточный кадр достраивается по скорости), B — опорный: перед каждым вызовом
// drvPoseValid = 0, то есть всегда полная поза (ровно прежний путь). Проверяем: чётные кадры A == B побитно; промежуточные — наибольшее отличие палитры
// (мало); смена клипа на жест руля/газа — полный пересчёт; выход (rootMode 0, ходьба) — поза A == B побитно.
//   tests/homer/driver_pose.sh [homer.shr]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "homer.h"
#include "skin.h"
static Homer A, B;
static float diff(const Homer *a, const Homer *b, int nj) {
  float d = 0.f; for (int j = 0; j < nj; j++) { const float *x = (const float *)&a->pal[j], *y = (const float *)&b->pal[j];
    for (int k = 0; k < 12; k++) d = fmaxf(d, fabsf(x[(k / 3) * 4 + k % 3] - y[(k / 3) * 4 + k % 3])); }
  float dp = 0.f; const float *p = (const float *)&a->place, *q = (const float *)&b->place; for (int k = 0; k < 16; k++) dp = fmaxf(dp, fabsf(p[k] - q[k]));
  return fmaxf(d, dp * 0.f + dp);
}
static void setup(Homer *H, SkinModel *m) { if (homerInit(H, m)) { printf("homerInit failed\n"); exit(1); } H->rootMode = 1; H->car.ok = 1; H->clip = H->cInCar; H->clipLoop = 1; H->clipT = 0.f; H->fade = H->fadeLen = 0.f; H->x = 10.f; H->y = 1.f; H->z = 5.f; H->h = 0.7f; }
int main(int argc, char **argv) {
  SkinModel *m = skinLoad(argc > 1 ? argv[1] : "build/homer.shr"); if (!m) { printf("no homer.shr\n"); return 1; }
  setup(&A, m); setup(&B, m); int nj = (int)m->h->nJoints; float dt = 1.f / 60.f, evenMax = 0.f, oddMax = 0.f, exitDiff = 0.f; int fresh = 0, mid = 0, bad = 0;
  for (int f = 0; f < 420; f++) {
    if (f == 200 && A.cDrvGas >= 0) { A.clip = B.clip = A.cDrvGas; A.clipLoop = B.clipLoop = 0; A.clipT = B.clipT = 0.f; }   // жест газа вместо покоя
    if (f == 240) { A.clip = B.clip = A.cInCar; A.clipLoop = B.clipLoop = 1; A.clipT = B.clipT = 0.f; }
    if (f == 360) { A.rootMode = B.rootMode = 0; A.clip = B.clip = -1; }   // выход из машины: ходьба
    float len = A.clip >= 0 ? skinClipLength(m, A.clip) : 0.f;
    if (A.clip >= 0) { A.clipT += dt; B.clipT += dt; if (A.clipLoop && len > 0.f) { A.clipT = fmodf(A.clipT, len); B.clipT = fmodf(B.clipT, len); } else if (A.clipT > len) A.clipT = B.clipT = len; }
    B.drvPoseValid = 0; homerPose(&B); homerPose(&A);
    float d = diff(&A, &B, nj);
    if (f >= 360) exitDiff = fmaxf(exitDiff, d);
    else if (A.drvPoseValid && A.drvPoseTick == 0) { fresh++; evenMax = fmaxf(evenMax, d); }
    else { mid++; oddMax = fmaxf(oddMax, d); }
  }
  printf("full frames %d (max diff vs reference %.6g), in-between %d (max diff %.6g), exit diff %.6g\n", fresh, evenMax, mid, oddMax, exitDiff);
  if (evenMax != 0.f) { printf("FAIL: full frames differ\n"); bad = 1; }
  if (exitDiff != 0.f) { printf("FAIL: pose after exit differs\n"); bad = 1; }
  if (oddMax > 0.05f) { printf("FAIL: in-between frames too far (>0.05)\n"); bad = 1; }
  // №520: машину сбросили (перенесли далеко), поза вне кадра не считалась — рамка водителя должна быть у машины, а не на старом месте
  { Homer C; setup(&C, m); float M[16] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 10,1,5,1}; memcpy(C.car.m, M, sizeof M); homerPose(&C);
    float far[16] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 500,3,-400,1}; memcpy(C.car.m, far, sizeof far);   // сброс: матрица машины новая, поза не считалась
    float bb[6]; int ok = homerDriverBox(&C, bb); float cx = (bb[0] + bb[3]) * .5f, cz = (bb[2] + bb[5]) * .5f, off = fabsf(cx - 500.f) + fabsf(cz + 400.f);
    printf("after reset: box centre %.1f %.1f (car 500 -400), off %.2f m\n", cx, cz, off);
    if (!ok || off > 4.f) { printf("FAIL: driver box stayed at the old place after the car reset (#520)\n"); bad = 1; } }
  if (!bad) printf("PASS\n"); return bad;
}
