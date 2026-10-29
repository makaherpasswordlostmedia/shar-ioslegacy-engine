// №902 (Роб 23.10: «разбивание стекла иногда отстаёт от удара: то вовремя, то поздно; с деревьями так же — анимация и звук в тот же
// кадр, что и удар, всегда»). Настоящие car.c/col.c/props.c/stateprops.c на данных уровня, без эмулятора и БЕЗ подмены остывания
// (tests/smash обнуляет cool каждый кадр — задержку не видит). Все стейтпропы, ловящие удар машины: заезд в лоб 12 направлений × 3 смещения
// × 5 / 10 / 18 м/с; кадр первого касания (взвелось остывание) против кадра события машины (hits). Печать: задержка в кадрах, доля > 0
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"
#include "../../viewer/stateprops.c"   // hitVolume (static): близость кузова к объёму предмета
unsigned homerSolidFrame = 0;
static Props props; static StateProps sp; static ColWorld world; static Car car;
static void quatR3(const float q[4], float R[9]) {
  float w = q[0], x = q[1], y = q[2], z = q[3];
  R[0] = 1 - 2 * (y * y + z * z); R[3] = 2 * (x * y - w * z); R[6] = 2 * (x * z + w * y);
  R[1] = 2 * (x * y + w * z); R[4] = 1 - 2 * (x * x + z * z); R[7] = 2 * (y * z - w * x);
  R[2] = 2 * (x * z - w * y); R[5] = 2 * (y * z + w * x); R[8] = 1 - 2 * (x * x + y * y);
}
static int carEvent(const StateProps *s, unsigned i) {
  const SpType *T = &s->type[s->inst[i].type]; const SpState *S = &s->state[T->firstState];
  for (unsigned k = 0; k < S->nEvent; k++) { int e = s->event[S->firstEvent + k].event; if (e == SP_EV_VEHICLE_HIT || e == SP_EV_HIT || e == SP_EV_DESTROYED) return 1; }
  return 0;
}
// -> задержка в кадрах (0 — в кадр касания), -1 — не коснулся / мир раньше, -2 — коснулся, события нет за 1,5 с
static int wallFirst, nearF;
static int nearVol(unsigned i, float pad) {   // кузов, раздутый на pad, касается объёма предмета
  CarBox cb; carBox(&car, &cb); cb.hl += pad; cb.hw += pad; const SpType *T = &sp.type[sp.inst[i].type];
  for (unsigned k = 0; k < T->nCol; k++) { float nx, nz, d, imp; if (hitVolume(&sp.run[i], &sp.col[T->firstCol + k], &cb, car.vel, &nx, &nz, &d, &imp)) return 1; }
  return 0;
}
static int drive(unsigned i, float x, float y, float z, float h, float v) {
  spFree(&sp); if (spInit(&sp, props.spr, props.sprSize)) return -1;
  carInit(&car, 0, &world, x, y, z, h); carSetSpeed(&car, v);
  CarInput in = {1.f, 0, 0, 0}; int first = -1; wallFirst = -1; nearF = -1;
  for (int n = 0; n < 60; n++) {
    carUpdate(&car, &world, &in, 1.f / 30.f);
    if (nearF < 0 && nearVol(i, .35f)) nearF = n;
    if (first < 0 && car.hardV > 1.f && wallFirst < 0) wallFirst = n;   // мир (стена COL1) раньше объёма пропа
    int h0 = sp.hits; float c0 = sp.run[i].cool;
    spUpdate(&sp, &world, &car, NULL, 1.f / 30.f);
    if (first < 0 && sp.run[i].cool > c0) first = n;   // первое касание: остывание взвелось
    if (sp.hits > h0 && nearF >= 0) return n - nearF;   // от подхода вплотную (кузов в 35 см от объёма)
    if (sp.hits > h0) return 0;   // 100+: задержка от удара о стену
    if (nearF >= 0 && n - nearF > 45) return -2;
  }
  return nearF < 0 ? -1 : -2;
}
int main(int argc, char **argv) {
  if (argc < 2) return 2; FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15); if (!data || fread(data, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40)) || !props.spr ||
      spInit(&sp, props.spr, props.sprSize)) { printf("нет стейтпропов\n"); return 0; }
  int tot = 0, late = 0, never = 0, hist[8] = {0}; unsigned ninst = sp.ninst;
  for (unsigned i = 0; i < ninst; i++) {
    const SpInst *I = &sp.inst[i]; const SpType *T = &sp.type[I->type];
    if (T->kind || T->cls == 2 || !T->nCol || I->tag || !carEvent(&sp, i)) continue;
    float R[9]; quatR3(I->q, R);
    float c[3] = {I->x + R[0] * T->c[0] + R[3] * T->c[1] + R[6] * T->c[2], I->y + R[1] * T->c[0] + R[4] * T->c[1] + R[7] * T->c[2], I->z + R[2] * T->c[0] + R[5] * T->c[1] + R[8] * T->c[2]};
    float ext = sqrtf(T->h[0] * T->h[0] + T->h[2] * T->h[2]) + 1.f;
    for (int a = 0; a < 12; a++) for (int o = -1; o <= 1; o++) for (int s = 0; s < 3; s++) {
      float ang = a * 0.5235988f, fx = sinf(ang), fz = cosf(ang), lat = o * .5f, d = ext + 6.f, v = s == 0 ? 5.f : s == 1 ? 10.f : 18.f;
      int r = drive(i, c[0] - fx * d + fz * lat, c[1] + 3.f, c[2] - fz * d - fx * lat, ang, v);
      if (argc > 2) printf("CASE %u %d %d %d %d\n", i, a, o, s, r);   // построчно для verdict.py: ключ заезда и результат (-1 не подошёл, -2 без события)
      if (r == -1) continue;
      tot++; if (r == -2) never++; else { late += r > 1; hist[r < 7 ? r : 7]++; }
    }
  }
  printf("подходов вплотную %d: событие за 0–1 кадр %d, позже %d (1:%d 2:%d 3:%d 4-6:%d 7+:%d), без события %d\n", tot, hist[0] + hist[1], late, hist[1], hist[2], hist[3], hist[4] + hist[5] + hist[6], hist[7], never);
  return 0;
}
