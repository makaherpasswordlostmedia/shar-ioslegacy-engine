#!/bin/bash
# 197 spawn/foot + moving chase census; 430 corrects the obsolete universal stand radius.
# No thresholds relaxed: 90/80m keepoff was an invalid requirement, replaced by recorded pursuit intent.
set -u
cd "$(dirname "$0")/../.."
OUT=build/hnr; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
$CC tests/hnr/police_host.c $BOTS_LIB -lm -o "$OUT/police" 2> "$OUT/build.txt" || { cat "$OUT/build.txt"; exit 2; }
"$OUT/police" $ARGS > "$OUT/police_new.txt"; green=$?
grep -E 'CHECK|RESULT|^stand:' "$OUT/police_new.txt"
$CC -DPOLICE_SPAWN_STRAIGHT=1 tests/hnr/police_host.c $BOTS_LIB -lm -o "$OUT/police_straight" 2> "$OUT/build.txt" || exit 2
"$OUT/police_straight" $ARGS > "$OUT/police_straight.txt"; old=$?
red=$(grep -c 'CHECK foot .*FAIL' "$OUT/police_straight.txt")
echo "197 old spawn foot failures=$red"
bash tests/hnr/chase430.sh; closing=$?
bash tests/hnr/levels/run.sh; levels=$?
if [ "$green" = 0 ] && [ "$old" = 1 ] && [ "$red" -gt 0 ] && [ "$closing" = 0 ] && [ "$levels" = 0 ]; then echo 'PASS police197+430'; exit 0; fi
echo "FAIL green=$green oldspawn=$old red=$red closing=$closing levels=$levels"; exit 1
