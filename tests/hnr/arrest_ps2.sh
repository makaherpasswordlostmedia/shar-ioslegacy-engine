#!/bin/bash
# №430 (ДОБИВКА 19): арест Hit & Run по 7 арестам PS2 — tests/hnr/arrest_ps2.c на функциях viewer/game.c, которые зовёт main.c.
# Эталон: tests/hnr/arrest_ps2_ref.h (из build/ps2ref/answers/b3_*/trace.tsv, tests/hnr/arrest_ps2_ref.py; sha256 в заголовке).
# ЗЕЛЁНЫЙ — новый код; КРАСНЫЙ — тот же гейт с -DARREST_PS2_OLD=1 (полиция через 0,6 с, таймер 1,5 с) обязан упасть. Хост, Мак, CPU
set -u
cd "$(dirname "$0")/../.."
OUT=${OUT:-build/arrest_ps2}; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I $V -I tools/bots -I tests/hnr"
for side in new old; do
  flags=''; [ "$side" = old ] && flags=-DARREST_PS2_OLD=1
  $CC $flags tests/hnr/arrest_ps2.c $BOTS_LIB -lm -o "$OUT/$side" 2> "$OUT/$side.cc" || { echo "FAIL: сборка $side"; head -5 "$OUT/$side.cc"; exit 2; }
  "$OUT/$side" > "$OUT/$side.log"; rc=$?
  echo "== $side (rc=$rc)"; grep -E 'FAIL|RESULT' "$OUT/$side.log"
  if [ "$side" = new ]; then g=$rc; else red=$rc; fi
done
if [ "$g" = 0 ] && [ "$red" = 1 ] && grep -q 'CHECK timer .*FAIL' "$OUT/old.log" && grep -q 'CHECK delay .*FAIL' "$OUT/old.log"; then
  echo 'PASS 430 arrest: PS2 delay/replay/timer green, ARREST_PS2_OLD red'; exit 0
fi
echo "FAIL 430 arrest green=$g old=$red"; exit 1
