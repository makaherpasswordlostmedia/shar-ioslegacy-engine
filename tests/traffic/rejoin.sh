#!/bin/bash
# V112: no restart after impact; the historical rear-axis gate is retained under OLD
set -u
cd "$(dirname "$0")/../.."
L=${1:-build/level.shr}; T=${2:-build/traffic.shr}; O=build/traffic-rejoin; mkdir -p "$O"
.venv/bin/python tests/traffic/stay112_source.py || exit 2
SRC="tests/traffic/rejoin.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c"
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I viewer"
$CC $SRC -lm -o "$O/new" || exit 2
$CC -DTRF_REJOIN_OLD=1 $SRC -lm -o "$O/old" || exit 2
$CC -DTRF_REJOIN_OLD=1 -DREJOIN_HISTORIC $SRC -lm -o "$O/history" || exit 2
$CC -DTRF_REJOIN_OLD=1 -DREJOIN_HISTORIC -DTRAFFIC_REJOIN_REAR_OLD $SRC -lm -o "$O/rear-old" || exit 2
"$O/new" "$L" "$T" > "$O/new.log"; g=$?
"$O/old" "$L" "$T" > "$O/old.log"; r=$?
"$O/history" "$L" "$T" > "$O/history.log"; h=$?
"$O/rear-old" "$L" "$T" > "$O/rear-old.log"; hr=$?
cat "$O/new.log" "$O/old.log" "$O/history.log" "$O/rear-old.log"
if [ $g = 0 ] && [ $r = 1 ] && [ $h = 0 ] && [ $hr = 1 ]; then
 echo 'PASS no restart / OLD caught; historical rear-axis correction preserved'; exit 0
fi
echo "FAIL new=$g old=$r historical=$h rearOLD=$hr";exit 1
