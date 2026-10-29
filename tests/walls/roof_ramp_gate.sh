#!/bin/bash
# №559: гейт въезда по скату крыши (J10-1, ящик COL1 17)
# Зелёный: ROOF_RAMP_OLD=0 — скат крыши не является стеной для колёс
# Красный: ROOF_RAMP_OLD=1 — колесо бьётся в скат крыши как в стену
set -e
cd "$(dirname "$0")/../.."
lvl="${1:-build/level.shr}"

clang -O2 -Iviewer -DROOF_RAMP_OLD=0 tests/walls/roof_ramp_test.c viewer/col.c -lm -o /tmp/roof_ramp_0
/tmp/roof_ramp_0 "$lvl"

clang -O2 -Iviewer -DROOF_RAMP_OLD=1 tests/walls/roof_ramp_test.c viewer/col.c -lm -o /tmp/roof_ramp_1
/tmp/roof_ramp_1 "$lvl"

echo "roof_ramp_gate: PASS (зелёный + красный контроль)"
