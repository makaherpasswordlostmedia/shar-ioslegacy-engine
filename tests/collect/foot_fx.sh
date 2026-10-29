#!/bin/bash
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/foot-fx; mkdir -p "$OUT"; PACK="${1:-build/collect-l1.shr}"
SRC="tests/collect/foot_fx.c viewer/collect.c viewer/stateprops.c viewer/col.c viewer/car.c viewer/coins.c viewer/homer.c viewer/skin.c"
cc -O2 -DSKIN_HOST -I viewer $SRC -lm -o "$OUT/green"
cc -O2 -DSKIN_HOST -DFOOT_FX_OLD=1 -I viewer $SRC -lm -o "$OUT/red"
"$OUT/green" "$PACK" | tee "$OUT/green.txt"
set +e
"$OUT/red" "$PACK" > "$OUT/red.txt"; rc=$?
set -e
[ "$rc" = 1 ] && grep -q 'kick=0.*shock=0' "$OUT/red.txt"
echo "PASS: lifecycle green; OLD missing both authored effects caught"
