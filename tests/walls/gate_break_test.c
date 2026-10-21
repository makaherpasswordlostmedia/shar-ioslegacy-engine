// №564: тест сбивания деревянных ворот у поля/огорода (L1 J3-6, l1_fence_Shape)
// Зелёный (GATE_BREAK_OLD=0): машина Гомера (1500 кг, 15 м/с) сбивает ворота с обеих сторон (N2S и S2N)
// Красный (GATE_BREAK_OLD=1): ворота требуют mass >= 3750 кг, машина Гомера блокируется
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"
#include "props.h"
#include "stateprops.h"

unsigned homerSolidFrame;

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "build/level.shr";
  FILE *f = fopen(path, "rb");
  if (!f && argc <= 1) {
    path = "/Users/USER/Downloads/shar-psp-sonnet-runs-w/build/final-20261011-1721/level.shr";
    f = fopen(path, "rb");
  }
  if (!f) {
    fprintf(stderr, "Error: cannot open level file %s\n", path);
    return 2;
  }
  fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
  char *buf = (char *)malloc(sz); fread(buf, 1, sz, f); fclose(f);
  unsigned co = *(unsigned *)(buf + 92), po = *(unsigned *)(buf + 96), pv = *(unsigned *)(buf + 88), ce = (unsigned)sz;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;

  ColWorld W;
  colInit(&W, buf + co, ce - co);
  Props props;
  propsInit(&props, buf + po, *(unsigned *)(buf + po + 40));

  StateProps sp;
  spInit(&sp, props.spr, props.sprSize);

  // Ищем экземпляр ворот у поля (192.48, -454.46)
  int fence_inst = -1;
  for (unsigned i = 0; i < sp.ninst; i++) {
    if (fabsf(sp.inst[i].x - 192.48f) < 1.5f && fabsf(sp.inst[i].z - -454.46f) < 1.5f) {
      fence_inst = (int)i;
      break;
    }
  }
  if (fence_inst < 0) {
    fprintf(stderr, "Error: fence instance near (192.48, -454.46) not found\n");
    free(buf);
    return 3;
  }

#if GATE_BREAK_OLD
  // В старой версии экспорт выставлял cls 11 для l1_fence_Shape
  ((SpType *)&sp.type[sp.inst[fence_inst].type])->cls = 11;
#endif

  // ЗАЕЗД 1: С севера на юг (heading PI, с дороги в поле)
  Car car;
  carInit(&car, NULL, &W, 192.48f, 3.0f, -446.0f, 3.14159f);
  carSetSpeed(&car, 15.0f);
  for (int step = 0; step < 40; step++) {
    CarInput in = { .throttle = 1.0f };
    carUpdate(&car, &W, &in, 1/60.f);
    propsUpdate(&props, &W, &car, 1/60.f);
    spUpdate(&sp, &W, &car, NULL, 1/60.f);
  }
  int n2s_broken = (sp.run[fence_inst].state != 0 && car.z < -455.0f);

  // ЗАЕЗД 2: С юга на север (heading 0, из поля на дорогу)
  spInit(&sp, props.spr, props.sprSize);
#if GATE_BREAK_OLD
  ((SpType *)&sp.type[sp.inst[fence_inst].type])->cls = 11;
#endif
  carInit(&car, NULL, &W, 192.48f, 3.0f, -462.0f, 0.0f);
  carSetSpeed(&car, 15.0f);
  for (int step = 0; step < 40; step++) {
    CarInput in = { .throttle = 1.0f };
    carUpdate(&car, &W, &in, 1/60.f);
    propsUpdate(&props, &W, &car, 1/60.f);
    spUpdate(&sp, &W, &car, NULL, 1/60.f);
  }
  int s2n_broken = (sp.run[fence_inst].state != 0 && car.z > -453.0f);

  free(buf);

#if GATE_BREAK_OLD
  if (!n2s_broken && !s2n_broken) {
    printf("RED CONTROL PASS: fence blocked car as expected when GATE_BREAK_OLD=1\n");
    return 0;
  } else {
    printf("RED CONTROL FAIL: fence broke when it should have blocked! (n2s=%d, s2n=%d)\n", n2s_broken, s2n_broken);
    return 1;
  }
#else
  if (n2s_broken && s2n_broken) {
    printf("GREEN TEST PASS: fence broken from both sides cleanly (n2s=%d, s2n=%d)\n", n2s_broken, s2n_broken);
    return 0;
  } else {
    printf("GREEN TEST FAIL: fence did not break from both sides! (n2s=%d, s2n=%d)\n", n2s_broken, s2n_broken);
    return 1;
  }
#endif
}
