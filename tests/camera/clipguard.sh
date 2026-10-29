#!/bin/bash
# CLIP_GUARD: tests/camera/clipguard.c. Красный -DCAM_CLIP_GUARD_OLD=1 обязан не пройти те же проверки.   tests/camera/clipguard.sh
set -u; cd "$(dirname "$0")/../.."; O=${TMPDIR:-/tmp}/clipg.$$
SRC="tests/camera/clipguard.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c"
cc -std=c11 -O1 -w -DSKIN_HOST -I viewer $SRC -lm -o $O.green || exit 2
cc -std=c11 -O1 -w -DSKIN_HOST -DCAM_CLIP_GUARD_OLD=1 -I viewer $SRC -lm -o $O.red || exit 2
$O.green | tail -4; g=${PIPESTATUS[0]}
$O.red > $O.red.txt; r=$?; echo "красный (прежнее): $(grep -c FAIL $O.red.txt) проверок не прошло"
rm -f $O.green $O.red $O.red.txt
[ $g = 0 ] && [ $r != 0 ] && { echo PASS; exit 0; } || { echo "FAIL (зелёный rc=$g, красный rc=$r)"; exit 1; }
