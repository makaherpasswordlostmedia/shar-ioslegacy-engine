#!/bin/bash
# Правка 424 / ОСТАТОК 09.10 п. 18 (tests/skid/neutral.c): сначала красный -DSKID_TINT_OLD=1, потом зелёный.  tests/skid/neutral.sh [LEVEL]
set -u; cd "$(dirname "$0")/../.."
OUT=build/skid; mkdir -p "$OUT"; LVL="${1:-build/level.shr}"
CC="cc -std=c11 -O2 -w -DSKID_HOST -I viewer"; SRC="tests/skid/neutral.c viewer/skid.c viewer/car.c viewer/col.c"
$CC -DSKID_TINT_OLD=1 $SRC -lm -o "$OUT/neutral_red" || exit 2; $CC $SRC -lm -o "$OUT/neutral" || exit 2
"$OUT/neutral_red" "$LVL" > "$OUT/neutral_red.txt"; rr=$?; echo "красный: $(grep -m1 'CHECK.*FAIL' "$OUT/neutral_red.txt" | cut -c1-160)"
echo "зелёный:"; "$OUT/neutral" "$LVL" | tee "$OUT/neutral.txt"; gr=${PIPESTATUS[0]}
[ $rr != 0 ] && [ $gr = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
