#!/bin/bash
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/bolts; mkdir -p "$OUT"; PACK="${1:-build/collect-l1.shr}"
SRC="tests/collect/bolts.c viewer/collect.c viewer/stateprops.c viewer/col.c viewer/car.c viewer/coins.c viewer/homer.c viewer/skin.c"
cc -O2 -DSKIN_HOST -I viewer $SRC -lm -o "$OUT/green"
cc -O2 -DSKIN_HOST -DWASP_BOLT_OLD=1 -I viewer $SRC -lm -o "$OUT/red"
"$OUT/green" "$PACK" | tee "$OUT/green.txt"
set +e
"$OUT/red" "$PACK" > "$OUT/red.txt"; rc=$?
set -e
[ "$rc" = 1 ] && grep -q '^FAIL delayed' "$OUT/red.txt" && grep -q '^FAIL moving dodge' "$OUT/red.txt"
echo "PASS: travel/hit/dodge green; instantaneous hit OLD caught"
