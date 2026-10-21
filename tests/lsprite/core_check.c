// Гейт №599 (ядро): таблица постоянного света строится из реальных данных SPR1 уровня тем же кодом, что в игре
// (viewer/lightsprite_core.h + viewer/stateprops.c). Проверки:
//  1) квад записи для 40 положений глаза = spBillQuad (прежний путь) до 1 мм — по всем записям уровня
//  2) запись «своя» только пока экземпляр на месте и в том же состоянии (сдвинули/сменили состояние — прежний путь)
//  3) плавное появление по дальности: нет скачка альфы больше 0,12 на метр хода глаза, при 100 м ноль, до 76 м единица
//  check LEVEL.shr HOMER.shr     RESULT: PASS|FAIL
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "lightsprite_core.h"

int main(int argc, char **argv) {
  if (argc < 3 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "usage: check level.shr homer.shr\n"); return 2; }
  static BotWorld w; if (bwNew(&w)) return 2;
  StateProps *sp = &w.sp; if (!w.haveSP) { printf("нет SPR1\nRESULT: FAIL\n"); return 1; }
  for (int f = 0; f < 30; f++) spUpdate(sp, bwCol(), NULL, NULL, BW_DT);
  static LspTab t; lspBuild(&t, sp, 0); lspFrameLive(&t, sp);
  int fails = 0; float worst = 0; unsigned own = 0;
  for (unsigned k = 0; k < t.n; k++) {
    const LspE *e = &t.e[k];
    if (!lspOwns(&t, e->inst, e->bill)) { fails++; printf("запись %u не своя при нетронутом экземпляре\n", k); continue; }
    own++;
    for (int s = 0; s < 40; s++) {
      float a = s * 0.157f, r = 5.f + 3.f * s;
      float ex = e->p[0] + r * cosf(a), ey = e->p[1] + 1.5f + (s % 7) * 2.f, ez = e->p[2] + r * sinf(a);
      float v0[12], v1[12]; uint32_t col, fl; int tx;
      spPose(sp, e->inst);
      if (!spBillQuad(sp, e->inst, e->bill, ex, ey, ez, v0, &col, &tx, &fl)) { fails++; printf("запись %u: прежний путь не рисует\n", k); break; }
      lspQuad(e, ex, ey, ez, v1);
      for (int j = 0; j < 12; j++) { float d = fabsf(v0[j] - v1[j]); if (d > worst) worst = d; if (d > 1e-3f) { if (fails < 20) printf("запись %u inst %u b %u mode %d: вершина %d разница %.4f\n", k, e->inst, e->bill, e->mode, j, d); fails++; j = 12; s = 40; } }
      if (col != e->abgr || tx != e->tex) { fails++; printf("запись %u: цвет/текстура не равны\n", k); }
    }
  }
  // 2) сдвиг экземпляра и смена состояния
  if (t.n) {
    unsigned i = t.e[0].inst; SpRun *r = &sp->run[i];
    r->x += 0.5f; lspFrameLive(&t, sp);
    if (lspOwns(&t, i, t.e[0].bill)) { fails++; printf("сдвинутый экземпляр остался своим\n"); }
    r->x -= 0.5f; lspFrameLive(&t, sp);
    if (!lspOwns(&t, i, t.e[0].bill)) { fails++; printf("вернувшийся экземпляр не стал своим\n"); }
    uint8_t s0 = r->state; r->state = (uint8_t)(s0 + 1); lspFrameLive(&t, sp);
    if (lspOwns(&t, i, t.e[0].bill)) { fails++; printf("экземпляр в другом состоянии остался своим\n"); }
    r->state = s0; r->alive = 0; lspFrameLive(&t, sp);
    if (lspOwns(&t, i, t.e[0].bill)) { fails++; printf("неживой экземпляр остался своим\n"); }
    r->alive = 1; lspFrameLive(&t, sp);
  }
  // 3) дальность
  float prev = lspFadeAt(0.f), maxStep = 0; int mono = 1;
  for (float d = 0.f; d <= 120.f; d += 1.f) { float f = lspFadeAt(d * d); if (fabsf(f - prev) > maxStep) maxStep = fabsf(f - prev); if (f > prev + 1e-6f) mono = 0; prev = f; }
  if (maxStep > 0.12f) { fails++; printf("скачок альфы по дальности %.3f на метр\n", maxStep); }
  if (!mono) { fails++; printf("альфа по дальности не убывает\n"); }
  if (lspFadeAt(100.f * 100.f) != 0.f || lspFadeAt(70.f * 70.f) != 1.f) { fails++; printf("края дальности\n"); }
  printf("записей %u (своих %u), худшее расхождение квада %.5f м, шаг альфы %.3f\n", t.n, own, worst, maxStep);
  printf("RESULT: %s\n", fails ? "FAIL" : "PASS");
  return fails ? 1 : 0;
}
