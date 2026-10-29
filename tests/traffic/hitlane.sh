#!/bin/bash
# Гейт аудита 09.10 п. 15/47 (tests/traffic/hitlane.c): сбитая машина трафика на боку не переносится на полосу.
#   КРАСНЫЙ 1: -DTRF_UPRIGHT_OLD=1 (прежнее) обязан упасть на side; КРАСНЫЙ 2: -DTRF_RAM_OLD=1 (до №479: не возвращается на полосу) — на upright; ЗЕЛЁНЫЙ: side и upright (№479: стоит ≈13,8 с и возвращается)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/hitlane; mkdir -p "$OUT"
SRC="tests/traffic/hitlane.c viewer/traffic.c viewer/col.c viewer/car.c viewer/skin.c viewer/homer.c"
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I viewer"
$CC -DTRF_REJOIN_OLD=1 -DTRF_UPRIGHT_OLD=1 $SRC -lm -o "$OUT/red" && $CC $SRC -lm -o "$OUT/green" || { echo "FAIL: сборка"; exit 2; }
"$OUT/red" > "$OUT/red.txt" 2>&1
if grep -q "CHECK side .*FAIL" "$OUT/red.txt"; then echo "красный: $(grep -m1 'CHECK side' "$OUT/red.txt")"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; cat "$OUT/red.txt"; red=0; fi
$CC -DTRF_RAM_OLD=1 $SRC -lm -o "$OUT/red2" || { echo "FAIL: сборка red2"; exit 2; }
"$OUT/red2" > "$OUT/red2.txt" 2>&1
if grep -q "CHECK upright .*FAIL" "$OUT/red2.txt"; then echo "красный 2: $(grep -m1 'CHECK upright' "$OUT/red2.txt")"; else echo "КРАСНЫЙ 2 (TRF_RAM_OLD) НЕ ПОЙМАН"; red=0; fi
"$OUT/green" > "$OUT/green.txt" 2>&1; rc=$?; cat "$OUT/green.txt"
[ $red = 1 ] && [ $rc = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
