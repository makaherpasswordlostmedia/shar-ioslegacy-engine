#!/bin/bash
# №400: снос задней оси машин трафика (tests/traffic/turns.c) — сначала красный (прежнее правило -DTRAFFIC_TURN_OLD), потом зелёный
#   tests/traffic/turns.sh [level.shr] [traffic.shr]
set -u; cd "$(dirname "$0")/../.."
L=${1:-build/level.shr}; T=${2:-build/traffic.shr}; O=${TMPDIR:-/tmp}/turns.$$
SRC="tests/traffic/turns.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c"
cc -std=c11 -O2 -w -DSKIN_HOST -DTRAFFIC_TURN_OLD -I viewer $SRC -lm -o $O.red || exit 2
cc -std=c11 -O2 -w -DSKIN_HOST -I viewer $SRC -lm -o $O.green || exit 2
r=$($O.red "$L" "$T"); rr=$?; g=$($O.green "$L" "$T"); gr=$?
echo "красный (прежнее): $r"; echo "зелёный: $g"; rm -f $O.red $O.green
[ $rr != 0 ] && [ $gr = 0 ] && { echo PASS; exit 0; } || { echo FAIL; exit 1; }
