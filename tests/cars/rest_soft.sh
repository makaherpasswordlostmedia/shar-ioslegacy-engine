#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
OUT=${OUT_DIR:-build/rest-soft-guard}
mkdir -p "$OUT"
cc -std=c11 -O2 -DCAR_REST_SLEEP_TEST -I viewer tests/cars/rest_soft.c viewer/car.c viewer/col.c -lm -o "$OUT/green"
"$OUT/green" > "$OUT/green.log"
cc -std=c11 -O2 -DCAR_REST_SLEEP_TEST -DCAR_REST_SOFT_OLD=1 -I viewer tests/cars/rest_soft.c viewer/car.c viewer/col.c -lm -o "$OUT/old"
if "$OUT/old" > "$OUT/old.log"; then echo 'FAIL soft sleep negative was accepted';exit 1;fi
grep -Eq '^support soft=1 idleSleep=[1-9]' "$OUT/old.log"
if grep -Eq 'firstFrameSleep=[1-9]' "$OUT/green.log";then echo 'FAIL input wake';exit 1;fi
cat "$OUT/green.log"
echo 'PASS actual soft sleep OLD rejected; gas/brake/handbrake wake in first frame'
