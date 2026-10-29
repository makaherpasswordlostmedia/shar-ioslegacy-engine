#!/bin/bash
# №339 остаток, J10-6 (193,1; 248,2; y 6,5): машина висит на кромке скоса носом вниз, газ и назад не сдвигают (PERCH_ESCAPE, car.c perchEscape).
# Гейт: рой tests/walls687/trap_swarm.c, L1, область (120 140 260 260), 700 заходов, зерно 5, цель — стоянка у (191…196; 246…250; y 6…7):
#   с правилом: ни одного кармана в цели; красный (-DPERCH_ESCAPE_OLD=1): >= 1.  Плюс: выводов с кромки на заходах при крене относительно земли < 10° нет по построению.
#   tests/walls687/perch_gate.sh LEVEL1.shr
set -u; cd "$(dirname "$0")/../.."; L=${1:?}; T=${TMPDIR:-/tmp}/perch_gate.$$
cc -std=c11 -O2 -w -Iviewer tests/walls687/trap_swarm.c viewer/car.c viewer/col.c -lm -o "$T.g" || exit 2
cc -std=c11 -O2 -w -DPERCH_ESCAPE_OLD=1 -Iviewer tests/walls687/trap_swarm.c viewer/car.c viewer/col.c -lm -o "$T.r" || exit 2
cnt() { TS_SECS=15 TS_TARGET=191,246,196,250,6,7 "$1" "$L" 120 140 260 260 700 5 | grep -c "^КАРМАН"; }
g=$(cnt "$T.g"); r=$(cnt "$T.r"); rm -f "$T.g" "$T.r"
echo "J10-6 с правилом: карманов в цели $g; красный (PERCH_ESCAPE_OLD=1): $r"
[ "$g" = 0 ] && [ "$r" -ge 1 ] && { echo "perch_gate: PASS"; exit 0; }; echo "perch_gate: FAIL"; exit 1
