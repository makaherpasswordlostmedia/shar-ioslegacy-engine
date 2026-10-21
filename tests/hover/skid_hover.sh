#!/bin/bash
# Гейт: следов шин под парящими машинами нет (правка 413). Мак, tests/hover/skid_hover_host.c; красный -DSKID_HOVER_OLD=1.
#   tests/hover/skid_hover.sh [LEVEL]   (по умолчанию build/level.shr — уровень 1: следы у порта сейчас только там)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/gates/413skid; mkdir -p "$OUT"; LVL="${1:-build/level.shr}"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -DSKID_HOST -I viewer"; SRC="tests/hover/skid_hover_host.c viewer/skid.c viewer/car.c viewer/col.c"
$CC -DSKID_HOVER_OLD=1 $SRC -lm -o "$OUT/red" 2> "$OUT/build.txt" && $CC $SRC -lm -o "$OUT/green" 2>> "$OUT/build.txt" || { echo "FAIL сборка"; head "$OUT/build.txt"; exit 2; }
echo "зелёный:"; "$OUT/green" "$LVL"; g=$?
echo "красный (-DSKID_HOVER_OLD=1):"; "$OUT/red" "$LVL"; r=$?
[ $g -eq 0 ] && [ $r -ne 0 ] && { echo "ИТОГ: PASS (красный пойман)"; exit 0; }; echo "ИТОГ: FAIL"; exit 1
