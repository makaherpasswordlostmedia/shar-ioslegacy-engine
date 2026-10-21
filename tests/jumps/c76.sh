#!/bin/bash
# №164 (L1 C7-6, «прозрачная стена в прыжке над гробом»): потеря скорости на въезде на ступени как у PS2 (28 -> 19,1 м/с к верху, потолок y 4,54). Красный: -DCAR_STEPLOSS_OLD=1.
#   tests/jumps/c76.sh [level.shr]
set -u; cd "$(dirname "$0")/.."/..; L=${1:-build/level.shr}; mkdir -p build/tmp
CC="cc -std=c11 -O2 -w -I viewer"
$CC -DCAR_STEPLOSS_OLD=1 tools/cartest/c76_stairs.c viewer/car.c viewer/col.c -lm -o build/tmp/c76_red && $CC tools/cartest/c76_stairs.c viewer/car.c viewer/col.c -lm -o build/tmp/c76_green || exit 2
build/tmp/c76_red "$L" > build/tmp/c76_red.txt; r=$?; build/tmp/c76_green "$L" > build/tmp/c76_green.txt; g=$?
cat build/tmp/c76_green.txt; echo "красный (STEPLOSS_OLD): $(tail -1 build/tmp/c76_red.txt)"
[ $r != 0 ] && [ $g = 0 ] && echo "PASS (красный пойман)" || { echo FAIL; exit 1; }
