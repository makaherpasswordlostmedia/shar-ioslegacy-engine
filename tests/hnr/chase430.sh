#!/bin/bash
set -u
cd "$(dirname "$0")/../.."
OUT=${OUT:-build/hnr430}; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC='cc -std=c11 -O2 -DSKIN_HOST -I viewer -I tools/bots -I tests/hnr'
for side in new old; do
  flags=''; [ "$side" = old ] && flags=-DPOLICE_CHASE_OLD=1
  $CC $flags tests/hnr/chase430.c $BOTS_LIB -lm -o "$OUT/$side" 2> "$OUT/$side.cc" || { cat "$OUT/$side.cc"; exit 2; }
  "$OUT/$side" build/ship_stage/level01.msn build/ship_stage/l2/level02.msn build/ship_stage/l3/level03.msn build/ship_stage/l4/level04.msn build/ship_stage/l5/level05.msn build/ship_stage/l6/level06.msn build/ship_stage/l7/level07.msn > "$OUT/$side.log"; r=$?
  cat "$OUT/$side.log"
  if [ "$side" = new ]; then g=$r; else red=$r; fi
done
if [ "$g" = 0 ] && [ "$red" = 1 ]; then echo 'PASS 430: actual pursuit closes, a292ed4 behavior red'; exit 0; fi
echo "FAIL 430 green=$g old=$red"; exit 1
