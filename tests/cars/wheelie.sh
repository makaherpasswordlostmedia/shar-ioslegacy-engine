#!/bin/bash
# №485: тест tests/cars/wheelie.c — Obliteratatron с места на полном газу не встаёт на дыбы (PS2 пик ~6°); красный -DWHEELIE_CAP_OLD=1 обязан упасть.   tests/cars/wheelie.sh -> PASS/FAIL
set -u; cd "$(dirname "$0")/../.."; O=${TMPDIR:-/tmp}/wh.$$
CC="cc -std=c11 -O2 -Wno-unused-function -DSKIN_HOST -I viewer tests/cars/wheelie.c viewer/car.c viewer/col.c -lm"
$CC -o $O.g || exit 2; $CC -DWHEELIE_CAP_OLD=1 -o $O.r || exit 2
$O.g oblit_v | grep -E "пик"; g=$?; $O.g oblit_v >/dev/null; gr=$?; $O.r oblit_v >/dev/null; rr=$?
rm -f $O.g $O.r
[ $gr = 0 ] && [ $rr != 0 ] && { echo "красный (-DWHEELIE_CAP_OLD=1) упал, как должен"; echo PASS; exit 0; } || { echo FAIL; exit 1; }
