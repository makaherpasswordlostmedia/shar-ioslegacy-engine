#!/bin/bash
# Проверка закрытия правок карты Роба №585 (крыша J10-1) и №586 (ворота поля J3-3, J3-6)
set -e
cd "$(dirname "$0")/../.."

echo "=== Проверка #585 (крыша J10-1) ==="
./tests/walls/roof_ramp_gate.sh

echo "=== Проверка #586 (ворота поля J3-6 и J3-3) ==="
./tests/walls/gate_break_gate.sh

# Дополнительно проверяем ворота J3-3 (Inst 99)
lvl="${1:-build/level.shr}"
if [ ! -f "$lvl" ]; then
  lvl="$HOME/Downloads/shar-psp/build/ship_stage/level.shr"
fi

cat << 'EOF' > /tmp/test_j33_gate.c
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
  const char *path = argv[1];
  FILE *f = fopen(path, "rb");
  if (!f) return 2;
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

  // Inst 99: ворота J3-3 (194.59, 4.93, -486.47)
  int fence_inst = 99;
#if GATE_BREAK_OLD
  ((SpType *)&sp.type[sp.inst[fence_inst].type])->cls = 11;
#endif

  // N2S
  Car car;
  carInit(&car, NULL, &W, 194.59f, 6.0f, -478.0f, 3.14159f);
  carSetSpeed(&car, 15.0f);
  for (int step = 0; step < 40; step++) {
    CarInput in = { .throttle = 1.0f };
    carUpdate(&car, &W, &in, 1/60.f);
    propsUpdate(&props, &W, &car, 1/60.f);
    spUpdate(&sp, &W, &car, NULL, 1/60.f);
  }
  int n2s_broken = (sp.run[fence_inst].state != 0 && car.z < -487.0f);

  // S2N
  spInit(&sp, props.spr, props.sprSize);
#if GATE_BREAK_OLD
  ((SpType *)&sp.type[sp.inst[fence_inst].type])->cls = 11;
#endif
  carInit(&car, NULL, &W, 194.59f, 6.0f, -494.0f, 0.0f);
  carSetSpeed(&car, 15.0f);
  for (int step = 0; step < 40; step++) {
    CarInput in = { .throttle = 1.0f };
    carUpdate(&car, &W, &in, 1/60.f);
    propsUpdate(&props, &W, &car, 1/60.f);
    spUpdate(&sp, &W, &car, NULL, 1/60.f);
  }
  int s2n_broken = (sp.run[fence_inst].state != 0 && car.z > -485.0f);
  free(buf);

#if GATE_BREAK_OLD
  if (!n2s_broken && !s2n_broken) {
    printf("RED CONTROL PASS: J3-3 fence blocked car when GATE_BREAK_OLD=1\n");
    return 0;
  }
  return 1;
#else
  if (n2s_broken && s2n_broken) {
    printf("GREEN PASS: J3-3 fence broken cleanly from both sides (n2s=1, s2n=1)\n");
    return 0;
  }
  return 1;
#endif
}
EOF

clang -O2 -Iviewer -DGATE_BREAK_OLD=0 /tmp/test_j33_gate.c viewer/stateprops.c viewer/props.c viewer/coins.c viewer/col.c viewer/car.c -lm -o /tmp/gate_j33_0
/tmp/gate_j33_0 "$lvl"

clang -O2 -Iviewer -DGATE_BREAK_OLD=1 /tmp/test_j33_gate.c viewer/stateprops.c viewer/props.c viewer/coins.c viewer/col.c viewer/car.c -lm -o /tmp/gate_j33_1
/tmp/gate_j33_1 "$lvl"

echo "=== Проверка #581 и #583 (стыки как прозрачные стены, холмы) ==="
./tests/walls/seam_wall_gate.sh

echo "=== Проверка #582 и #584 (ямы L2, выступы L3) ==="
./tests/walls/pits_ridges_gate.sh

echo "=== Проверка #587 и #590 (кусты J9-4, неиграбельные зоны K3-3, L3) ==="
./tests/walls/zones_bushes_gate.sh

echo "=== Проверка #588 и #589 (сбиваемое: гидрант, заборчики, пропы; фейд сбитых) ==="
./tests/walls/props_break_gate.sh

echo "karta_branch_verify_gate: PASS (585, 586, 581, 583, 582, 584, 587, 590, 588, 589 проверены: зелёный + красный контроль)"
