#!/bin/bash
# Гейт взаимодействий с красным контролем (правка Роба 71, 01.10: «не могу поехать налево и разбить стекло»).
# КРАСНЫЙ: стекло без обломка (-DGLASS_NO_BREAK, onKick -> 0) — проезд сквозь стекло его не бьёт, гейт обязан упасть.
# ЗЕЛЁНЫЙ: tests/interactions/host.c как есть (стёкла, возврат пропов, RESET CAR, посадка Гомера, проезд сквозь стекло).
#   tests/interactions/run.sh [level.shr] [homer.shr]
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/interactions-run; mkdir -p "$OUT"
LVL="${1:-build/level.shr}"; HOM="${2:-build/homer.shr}"
SRC="tests/interactions/host.c viewer/props.c viewer/stateprops.c viewer/col.c viewer/car.c viewer/coins.c viewer/homer.c viewer/skin.c"
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I viewer"
# shellcheck disable=SC2086
$CC -DGLASS_NO_BREAK $SRC -lm -o "$OUT/host-red" && $CC $SRC -lm -o "$OUT/host" || exit 2
fail=0
"$OUT/host-red" "$LVL" "$HOM" > "$OUT/red.txt" 2>&1
if [ $? -ne 0 ] && grep -q "FAIL driving through a pane breaks it" "$OUT/red.txt"; then echo "красный (стекло без обломка): упал, как должен"
else echo "КРАСНЫЙ НЕ ПОЙМАН: стекло без обломка прошло"; fail=1; fi
"$OUT/host" "$LVL" "$HOM" > "$OUT/green.txt" 2>&1 || fail=1
grep -E "glass drive|pane |FAIL|RESULT" "$OUT/green.txt"
[ $fail -eq 0 ] && { echo "PASS: красный пойман, зелёный"; exit 0; }
echo "FAIL"; exit 1
