#!/bin/bash
# Правка Роба 249: следы шин на Маке (tests/skid/host.c — тот же car.c, col.c, skid.c, что на PSP; уровень build/level.shr).
#   tests/skid/host.sh [LEVEL]   сначала красный (-DSKID_MARKS=0, прежнее: следов нет) — обязан упасть, потом зелёный
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/skid; mkdir -p "$OUT"; LVL="${1:-build/level.shr}"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -DSKID_HOST -I viewer"
SRC="tests/skid/host.c viewer/skid.c viewer/car.c viewer/col.c"
$CC -DSKID_MARKS=0 $SRC -lm -o "$OUT/host_red" 2> "$OUT/host_build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/host_build.txt"; exit 1; }
if "$OUT/host_red" "$LVL" > "$OUT/host_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: прежнее прошло"; red=0
else echo "красный: $(grep -c '^FAIL' "$OUT/host_red.txt") провал(ов): $(grep '^FAIL' "$OUT/host_red.txt" | cut -c6-60 | tr '\n' ';')"; red=1; fi
$CC $SRC -lm -o "$OUT/host" 2> "$OUT/host_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/host_build.txt"; exit 1; }
echo "зелёный:"; "$OUT/host" "$LVL" > "$OUT/host.txt" 2>&1; green=$?; cat "$OUT/host.txt"
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
