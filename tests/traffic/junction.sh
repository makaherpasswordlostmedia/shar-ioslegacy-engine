#!/bin/bash
# ОСТАТОК 09.10 п. 17: в занятый перекрёсток не въезжать (viewer/traffic.c TRAFFIC_JUNC_OLD). Прогон tests/traffic/host.c
# (5 мест L1, 900 кадров, темп трафика по PS2): строка «frames with two driving cars overlapping». Красный -DTRAFFIC_JUNC_OLD=1
# (после JAM_WAIT въезд в занятый) обязан дать наложения > 0, зелёный — 0.   tests/traffic/junction.sh [level.shr] [traffic.shr]
set -u; cd "$(dirname "$0")/../.."
L=${1:-build/level.shr}; T=${2:-build/traffic.shr}; O=${TMPDIR:-/tmp}/junc.$$
SRC="tests/traffic/host.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c"
ov() { "$1" "$L" "$T" build/homer.shr 2>/dev/null | awk '/== real data/{r=1} r && /two driving cars overlapping/{print $(NF-1); exit}'; }
cc -std=c11 -O2 -w -DSKIN_HOST -DTRAFFIC_JUNC_OLD=1 -I viewer $SRC -lm -o $O.red || exit 2
cc -std=c11 -O2 -w -DSKIN_HOST -I viewer $SRC -lm -o $O.green || exit 2
r=$(ov $O.red); g=$(ov $O.green); rm -f $O.red $O.green
echo "кадров наложения едущих машин: красный (въезд в занятый после 4 с) $r, зелёный $g"
awk -v r="$r" -v g="$g" 'BEGIN{exit !(r+0 > 0 && g == "0.000")}' && { echo PASS; exit 0; } || { echo FAIL; exit 1; }
