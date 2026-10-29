// Каждый предмет уровня под ударом (пункт 10а docs/handoff/LOOP_TERMINAL.md): тот же кадр, что viewer/main.c
// (carUpdate -> propsUpdate -> spUpdate; сбитый DynaPhys ломается через spBreak, как onPropKick). Без AI.
// Для каждого экземпляра PRP1 и каждого стейтпропа SPR1 (kind 0): машина подъезжает с 8 курсов на 20, 50 и 90 км/ч
// (старт в 12 м, уже на скорости, газ держит скорость) и одно падение сверху с 5 м; 3 с на заезд. Потом отдельно
// возврат: удар на 50 км/ч, машина уезжает, 7 с «вне вида» (propsRespawnStep / spRespawnStep со взглядом издалека).
// Строка на заезд (TSV) в stdout:
//   P|S  inst type heading kmh  kicked broken moved_m flew  state0 state1 alive colOn coins  carStuck reach_m stuckWithout
//        [P: propVmax carVmax — пик скорости предмета и машины за заезд, м/с; propHmax — пик по горизонтали (удар),
//         drop — насколько предмет ушёл ниже своего места, void — в конце под ним нет земли коллизии (упал в дыру)]
// --plant-kick K (после part parts): отрицательный контроль — в кадр удара скорость предмета × K (аномалия обязана найтись)
//   B    тип PRP1, номер типа-обломка SPR1 (-1 нет), кусков у обломка (0 — обломок только эффект: вода гидранта, предмет не исчезает)
// (заезд 5 с; stuckWithout — тот же заезд без предмета: упирается ли машина в окружение, а не в предмет)
//   R    P|S inst type  restored
//   cc -std=c11 -O2 -DSKIN_HOST -I viewer tools/cartest/props_sweep.c viewer/car.c viewer/col.c viewer/props.c \
//      viewer/stateprops.c viewer/coins.c -lm -o build/props_sweep ;  build/props_sweep level.shr [K N]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"

static Props props; static StateProps sp; static ColWorld world; static Car car;
static PropState *st0; static int kicked;
static int onKick(void *u, unsigned i, float dx, float dz) {
  (void)u; (void)dx; (void)dz; kicked = 1;
  int b = spBreakOf(&sp, props.def[i].type); if (b < 0) return 0;
  float pos[3] = {props.def[i].x, props.def[i].y, props.def[i].z};
  return spBreak(&sp, (unsigned)b, pos, props.def[i].q);
}
static int never(void *u, float x, float y, float z, float r) { (void)u; (void)x; (void)y; (void)z; (void)r; return 0; }
static void reset(void) {
  memcpy(props.st, st0, sizeof(PropState) * props.ninst); props.havePreviousCar = 0;
  spFree(&sp); if (spInit(&sp, props.spr, props.sprSize)) exit(2);
}
// заезд к точке (tx, ty, tz) с курса a на kmh (kmh < 0 — падение сверху с 5 м); -> застряла ли машина;
// *reach — ближе всего центр кузова подходил к точке (м)
static float reachM, propVmax, carVmax, propHmax, propYmin, plantK = 1.f; static int watchI = -1, plantDone;
static float reachYlo = -1e9f, reachYhi = 1e9f;   // «дошла» — только если кузов по высоте перекрывает предмет (PRP1)   // наблюдение: пик скорости предмета и машины за заезд
static int trial(float tx, float ty, float tz, float a, float kmh, float secs) {
  float sx, sz, gy, h;
  reachM = 1e9f; propVmax = carVmax = propHmax = 0.f; propYmin = 1e9f; plantDone = 0;   // до любого выхода: без старта заезда нет
  if (kmh < 0) {
    sx = tx; sz = tz; h = 0.3f;
    if (!colGround(&world, sx, sz, ty + 1.5f, ty - 6.f, &gy, 0)) gy = ty;
    carInit(&car, NULL, &world, sx, gy, sz, h); car.y = ty + 5.f; car.ry = car.y;
  } else {
    sx = tx - sinf(a) * 12.f; sz = tz - cosf(a) * 12.f; h = a;
    if (!colGround(&world, sx, sz, ty + 3.f, ty - 6.f, &gy, 0)) return -1;
    carInit(&car, NULL, &world, sx, gy, sz, h);
    for (int k = 0; k < 5; k++) { CarInput in = {0}; carUpdate(&car, &world, &in, 1 / 60.f); }
    carSetSpeed(&car, kmh / 3.6f);
  }
  float x0 = car.x, z0 = car.z;
  for (int fr = 0; fr < secs * 60; fr++) {
    CarInput in = {0}; in.throttle = kmh > 0 && car.v * 3.6f < kmh ? 1.f : 0.f;
    carUpdate(&car, &world, &in, 1 / 60.f); propsUpdate(&props, &world, &car, 1 / 60.f); spUpdate(&sp, &world, &car, NULL, 1 / 60.f);
    CarBox b; carBox(&car, &b); float d = hypotf(b.x - tx, b.z - tz); if (b.y + b.hi < reachYlo || b.y + b.lo > reachYhi) d = 1e9f; if (d < reachM) reachM = d;
    float cv = sqrtf(car.vel[0] * car.vel[0] + car.vel[1] * car.vel[1] + car.vel[2] * car.vel[2]); if (cv > carVmax) carVmax = cv;
    if (watchI >= 0 && plantK != 1.f && !plantDone && !props.st[watchI].asleep) { float *pv = props.st[watchI].vel; pv[0] *= plantK; pv[2] *= plantK; plantDone = 1; }
    if (watchI >= 0 && !props.st[watchI].hidden) { const float *pv = props.st[watchI].vel; float v = sqrtf(pv[0] * pv[0] + pv[1] * pv[1] + pv[2] * pv[2]); if (v > propVmax) propVmax = v;
      float hv = sqrtf(pv[0] * pv[0] + pv[2] * pv[2]); if (hv > propHmax) propHmax = hv; if (props.st[watchI].y < propYmin) propYmin = props.st[watchI].y; }
  }
  return kmh > 0 && hypotf(car.x - x0, car.z - z0) < 6.f;   // не проехала и 6 м из 36 — упёрлась
}

int main(int argc, char **argv) {
  if (argc < 2) return 2;
  int part = argc > 3 ? atoi(argv[2]) : 0, parts = argc > 3 ? atoi(argv[3]) : 1;
  for (int k = 4; k + 1 < argc; k++) if (!strcmp(argv[k], "--plant-kick")) plantK = (float)atof(argv[k + 1]);
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15);
  if (!data || fread(data, 1, size, f) != (size_t)size) return 2;
  fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40)) ||
      spInit(&sp, props.spr, props.sprSize)) return 2;
  props.onKick = onKick;
  st0 = malloc(sizeof(PropState) * props.ninst); memcpy(st0, props.st, sizeof(PropState) * props.ninst);
  const float kmhs[3] = {20, 50, 90};
  int job = 0;
  // типы SPR1 для сверки порядка с экспортёром: kind/bindex/cls
  if (part == 0) for (unsigned t = 0; t < props.ntype; t++) {   // обломок SPR1 у типа PRP1 и есть ли у него куски (без кусков — только эффект)
    int b = spBreakOf(&sp, t); printf("B\t%u\t%d\t%u\n", t, b, b >= 0 ? sp.type[b].nPiece : 0u); }
  if (part == 0) for (unsigned t = 0; t < sp.ntype; t++) { const SpType *T = &sp.type[t]; printf("T\t%u\t%u\t%u\t%u\n", t, T->kind, T->bindex, T->cls); }
  for (unsigned i = 0; i < props.ninst; i++) {
    if (job++ % parts != part) continue;
    const PropDef *D = &props.def[i];
    for (int k = 0; k <= 24; k++) {
      float a = (k % 8) * 0.7854f, kmh = k < 24 ? kmhs[k / 8] : -1.f;
      reset(); props.st[i].hidden = 1;                                  // тот же заезд без предмета: упирается ли и так
      int stuck0 = trial(D->x, D->y, D->z, a, kmh, 5.f);
      reset(); kicked = 0; watchI = (int)i;
      { const PropState *q = &props.st[i]; reachYlo = q->y - q->hy - .3f; reachYhi = q->y + q->hy + .3f; }   // коробка стоит (hy — по высоте)
      int stuck = trial(D->x, D->y, D->z, a, kmh, 5.f);
      float reach = reachM; watchI = -1; reachYlo = -1e9f; reachYhi = 1e9f;
      const PropState *s = &props.st[i];
      float moved = sqrtf((s->x - D->x) * (s->x - D->x) + (s->z - D->z) * (s->z - D->z));
      int flew = moved > 80.f || s->y > D->y + 20.f;
      float g; int hasG = colGround(&world, s->x, s->z, s->y + 1.f, -1e6f, &g, 0);
      printf("P\t%u\t%u\t%.0f\t%.0f\t%d\t%d\t%.1f\t%d\t0\t0\t0\t0\t0\t%d\t%.2f\t%d\t%.2f\t%.2f\t%.2f\t%.1f\t%d\n", i, D->type, a * 57.2958f, kmh, kicked, s->hidden, moved, flew,
             stuck, reach, stuck0, propVmax, carVmax, propHmax, propYmin < 1e8f ? D->y - propYmin : 0.f, !s->hidden && !hasG);
    }
    reset(); kicked = 0; trial(D->x, D->y, D->z, 0.f, 50.f, 1.5f);
    int was = props.st[i].hidden || hypotf(props.st[i].x - D->x, props.st[i].z - D->z) > 0.5f;
    for (int n = 0; n < 7 * 20; n++) propsRespawnStep(&props, D->x + 500.f, D->z + 500.f, 0.05f, never, 0);
    const PropState *s = &props.st[i];
    int back = !s->hidden && hypotf(s->x - D->x, s->z - D->z) < 0.2f;
    printf("R\tP\t%u\t%u\t%d\t%d\n", i, D->type, was, back);
  }
  for (unsigned j = 0; j < sp.ninst; j++) {
    const SpType *T = &sp.type[sp.inst[j].type]; if (T->kind != 0) continue;
    if (job++ % parts != part) continue;
    const SpInst *I = &sp.inst[j];
    for (int k = 0; k <= 24; k++) {
      float a = (k % 8) * 0.7854f, kmh = k < 24 ? kmhs[k / 8] : -1.f;
      reset(); sp.run[j].alive = 0; sp.run[j].colOn = 0;                  // тот же заезд без предмета
      int stuck0 = trial(I->x, I->y, I->z, a, kmh, 5.f);
      reset();
      unsigned c0 = (unsigned)sp.coins; int s0 = sp.run[j].state;
      int stuck = trial(I->x, I->y, I->z, a, kmh, 5.f);
      float reach = reachM;
      const SpRun *r = &sp.run[j];
      float moved = sqrtf((r->x - I->x) * (r->x - I->x) + (r->z - I->z) * (r->z - I->z));
      printf("S\t%u\t%u\t%.0f\t%.0f\t0\t0\t%.1f\t0\t%d\t%d\t%d\t%d\t%u\t%d\t%.2f\t%d\n", j, I->type, a * 57.2958f, kmh, moved, s0, r->state, r->alive, r->colOn,
             (unsigned)sp.coins - c0, stuck, reach, stuck0);
    }
    reset(); trial(I->x, I->y, I->z, 0.f, 50.f, 1.5f);
    int was = sp.run[j].state != 0 || !sp.run[j].alive || !sp.run[j].colOn;
    for (int n = 0; n < 7 * 20; n++) spRespawnStep(&sp, I->x + 500.f, I->z + 500.f, 0.05f, never, 0);
    int back = sp.run[j].state == 0 && sp.run[j].alive && sp.run[j].colOn;
    printf("R\tS\t%u\t%u\t%d\t%d\n", j, I->type, was, back);
  }
  return 0;
}
