#!/bin/bash
# Гейт гравитации машины (tests/cars/gravity.c, аудит 09.10 п. 34). КРАСНЫЙ: -DGRAV_RED=15 (прежнее число порта) обязан упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gravity; mkdir -p "$OUT"
SRC="tests/cars/gravity.c viewer/car.c viewer/col.c"; CC="cc -std=c11 -O2 -w -DSKIN_HOST -I viewer"
$CC -DGRAV_RED=15.f $SRC -lm -o "$OUT/red" && $CC $SRC -lm -o "$OUT/green" || { echo "FAIL: сборка"; exit 2; }
"$OUT/red" > "$OUT/red.txt" 2>&1; rr=$?
if [ $rr -ne 0 ] && grep -q "CHECK gravity FAIL" "$OUT/red.txt"; then echo "красный: $(grep '^PS2' "$OUT/red.txt")"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; cat "$OUT/red.txt"; red=0; fi
"$OUT/green" > "$OUT/green.txt" 2>&1; rc=$?; cat "$OUT/green.txt"
[ $red = 1 ] && [ $rc = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
