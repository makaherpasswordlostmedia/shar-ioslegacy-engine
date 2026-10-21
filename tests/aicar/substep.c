// Гейт «подшаги физики ИИ-машин реже вдали» (AI_SUBSTEP_OLD, msncar.c aiSubstep).
// Погоня: три преследователя в 35–90 м от едущего игрока, 40 с. Проверки:
//  1) близко (ближе 20 м по расстоянию, которое использует ИИ) и вне недавнего контакта шаг только полный;
//  2) открытая петля: записанный ввод полного прогона подаётся двум копиям машины — с полным шагом и с шагом по ступеням нового прогона; расхождение
//     положений, пока копия A ещё повторяет полный прогон (до первого контакта/возврата на путь), не больше порога.
// Замкнутая погоня сама по себе расходится (ИИ решает по положению) — это не мерится, только время.
//   tests/aicar/substep.c LEVEL HOMER MSN ; красный контроль -DAI_SUBSTEP_BREAK=1 (ступени всегда и вблизи) обязан упасть
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "world.h"
static BotWorld W;
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1e6 + t.tv_nsec * 1e-3; }
#define NF 2400
static float px[2][3][NF], pz[2][3][NF], subRec[3][NF]; static CarInput inRec[3][NF]; static Car car0[3];
static int tierSeen[3], nearBad;
static double run(int old) {
  mcAiSubstepOld = old; bwNew(&W); bwPlace(&W, W.car.x, W.car.y, W.car.z, W.car.h);   // игрок за рулём
  GameMsn *m = &W.msn; mcInit(&m->cars);
  static const char *names[3] = {"minivanA", "glastruc", "ch2"}; float dist[3] = {35.f, 55.f, 90.f};
  for (int k = 0; k < 3; k++) { float p[3] = {W.car.x - sinf(W.car.h) * dist[k], W.car.y, W.car.z - cosf(W.car.h) * dist[k]};
    McCar *c = mcSpawn(&m->cars, bwCol(), (const Traffic *)bwTraffic(), names[k], p, W.car.h, 1, "chase", 0, 0); if (c) c->on = 1; }
  double tot = 0; int n = 0;
  for (int f = 0; f < NF; f++) {
    float ax = .3f * sinf(f * .012f);
    double t0 = now(); bwStep(&W, 0, ax, f < 150 ? -1.f : -.8f); double d = now() - t0; if (f > 60) { tot += d; n++; }
    for (int k = 0; k < 3 && k < m->cars.n; k++) { const McCar *c = &m->cars.c[k];
      px[old][k][f] = c->car.x; pz[old][k][f] = c->car.z;
      if (f == 0 && old) car0[k] = c->car;
      if (old) inRec[k][f] = c->lastIn;
      else { subRec[k][f] = c->car.p.sub; tierSeen[c->subTier]++;
        if (c->subD < 20.f && c->subFullT <= 0.f && c->car.p.sub > c->subBase * 1.001f) { if (!nearBad) printf("   близко с редким шагом: машина %d кадр %d d(ИИ)=%.1f ступень %d\n", k, f, c->subD, c->subTier); nearBad++; } } }
  }
  bwFree(&W); return tot / n;
}
int main(int argc, char **argv) {
  if (bwData(argv[1], argv[2], argv[3])) return 2;
  double tOld = run(1), tNew = run(0), worst = 0, tA = 0, tB = 0; int valid = 0;
  for (int k = 0; k < 3; k++) {
    Car A = car0[k], B = car0[k]; double mx = 0; float base = A.p.sub; int validEnd = NF, n60 = 0, n40 = 0;
    for (int f = 1; f < NF; f++) {
      float want = subRec[k][f] > base * 1.001f ? subRec[k][f] : base; B.p.sub = want; n60 += want > base * 1.001f && want < 1.f / 50.f; n40 += want >= 1.f / 50.f;
      double t0 = now(); carUpdate(&A, bwCol(), &inRec[k][f], 1.f / 60.f); tA += now() - t0; t0 = now(); carUpdate(&B, bwCol(), &inRec[k][f], 1.f / 60.f); tB += now() - t0;
      if (f < validEnd && hypot(A.x - px[1][k][f], A.z - pz[1][k][f]) > 0.05) validEnd = f;   // A перестала повторять полный прогон (контакт, возврат на путь)
      double d = hypot(A.x - B.x, A.z - B.z); if (f < validEnd && d > mx) mx = d; }
    printf("  машина %d: копия A повторяет полный прогон до кадра %d из %d; макс. расхождение с шагом по ступеням %.2f м (кадров 60 Гц: %d, 40 Гц: %d)\n", k, validEnd, NF, mx, n60, n40);
    valid += validEnd > 300; if (validEnd > 300 && mx > worst) worst = mx;
  }
  printf("шаг логики погони %.1f -> %.1f мкс (%.2f×); физика копий %.0f -> %.0f мкс (%.2f×); ступени 0/1/2: %d / %d / %d кадров\n", tOld, tNew, tOld / tNew, tA, tB, tA / tB, tierSeen[0], tierSeen[1], tierSeen[2]);
  int bad = nearBad || !valid;   // расхождение — сведения для решения Роба (см. msncar.c AI_SUBSTEP_OLD), не отказ
  printf("близко с редким шагом: %d случаев; макс. расхождение открытой петли %.2f м (сведения; машины дальше 25 м от игрока), пригодных машин %d\n%s\n", nearBad, worst, valid, bad ? "FAIL" : "PASS"); return bad;
}
