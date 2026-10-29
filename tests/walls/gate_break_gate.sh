#!/bin/bash
# №564: гейт сбивания деревянных ворот у поля/огорода (L1 J3-6, l1_fence_Shape)
# Зелёный: GATE_BREAK_OLD=0 — деревянные ворота сбиваются машиной с обеих сторон (N2S и S2N)
# Красный: GATE_BREAK_OLD=1 — деревянные ворота блокируют лёгкие машины как каменная стена
set -e
cd "$(dirname "$0")/../.."
lvl="${1:-build/level.shr}"

clang -O2 -Iviewer -DGATE_BREAK_OLD=0 tests/walls/gate_break_test.c viewer/stateprops.c viewer/props.c viewer/coins.c viewer/col.c viewer/car.c -lm -o /tmp/gate_break_0
/tmp/gate_break_0 "$lvl"

clang -O2 -Iviewer -DGATE_BREAK_OLD=1 tests/walls/gate_break_test.c viewer/stateprops.c viewer/props.c viewer/coins.c viewer/col.c viewer/car.c -lm -o /tmp/gate_break_1
/tmp/gate_break_1 "$lvl"

echo "gate_break_gate: PASS (зелёный + красный контроль)"
