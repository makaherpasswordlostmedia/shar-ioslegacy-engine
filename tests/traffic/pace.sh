#!/bin/bash
# ОСТАТОК 09.10 п. 17 (аудит п. 22): ход трафика против трасс близнеца PS2 (tests/traffic/pace.c). Сначала красный
# -DTRAFFIC_PACE_OLD=1, потом зелёный.   tests/traffic/pace.sh [level.shr] [traffic.shr]
set -u; cd "$(dirname "$0")/../.."
L=${1:-build/level.shr}; T=${2:-build/traffic.shr}; O=${TMPDIR:-/tmp}/pace.$$
SRC="tests/traffic/pace.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c"
cc -std=c11 -O2 -w -DSKIN_HOST -DTRAFFIC_PACE_OLD=1 -I viewer $SRC -lm -o $O.red || exit 2
cc -std=c11 -O2 -w -DSKIN_HOST -I viewer $SRC -lm -o $O.green || exit 2
$O.red "$L" "$T" > $O.red.txt; rr=$?; echo "красный (прежнее): $(grep -m1 'CHECK.*FAIL' $O.red.txt | cut -c1-200)"
echo "зелёный:"; $O.green "$L" "$T" | tee $O.green.txt | grep -E "CHECK|RESULT"; gr=${PIPESTATUS[0]}
cc -std=c11 -O2 -w -DSKIN_HOST -DTRAFFIC_PACE_K_OLD=1 -I viewer $SRC -lm -o $O.k || exit 2
$O.k "$L" "$T" > $O.k.txt; kr=$?; echo "красный №624 (1,25): $(grep -m1 'CHECK.*FAIL' $O.k.txt | cut -c1-120)"
rm -f $O.k $O.k.txt $O.red $O.green $O.red.txt $O.green.txt
[ $rr != 0 ] && [ $kr != 0 ] && [ $gr = 0 ] && { echo PASS; exit 0; } || { echo FAIL; exit 1; }
