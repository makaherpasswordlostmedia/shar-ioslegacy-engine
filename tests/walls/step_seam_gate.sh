#!/bin/bash
# tests/walls/step_seam_gate.sh [L3.shr [L6.shr]] — правка Роба 607 (L3 C7-4 причал): шов-ступень не подбрасывает машину; L3 и L6 (одна карта)
# Красный контроль: -DSTEP_SEAM_OLD=1 обязан упасть. Порог «26 событий» — число прежнего кода на L3 (15.10)
set -u
cd "$(dirname "$0")/../.."
OUT=build/tmp/step_seam; mkdir -p "$OUT"
L3=${1:-build/levels/l3/level.shr}; L6=${2:-build/levels/l6/level.shr}
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -I viewer"
$CC tests/walls/step_seam_test.c viewer/col.c viewer/car.c -lm -o "$OUT/green" || exit 2
$CC -DSTEP_SEAM_OLD=1 tests/walls/step_seam_test.c viewer/col.c viewer/car.c -lm -o "$OUT/red" || exit 2
bad=0
for L in "$L3" "$L6"; do
  [ -f "$L" ] || { echo "нет $L"; bad=1; continue; }
  echo "зелёный $L: $("$OUT/green" "$L" | tail -2 | tr '\n' ' ')"; "$OUT/green" "$L" > /dev/null || bad=1
  "$OUT/red" "$L" > /dev/null && { echo "КРАСНЫЙ КОНТРОЛЬ НЕ ПОЙМАН ($L)"; bad=1; } || echo "красный контроль (STEP_SEAM_OLD=1) упал, как должен: $L"
done
[ $bad = 0 ] && echo "step_seam_gate: PASS" || echo "step_seam_gate: FAIL"; exit $bad
