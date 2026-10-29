#!/bin/bash
set -eu
cd "$(dirname "$0")/../../.."
OUT=${FUSE385_OUT:-build/fuse385-host-proof}
mkdir -p "$OUT"
cc -std=c11 -O2 -Wall tests/load/fuse385/host.c -o "$OUT/new"
cc -std=c11 -O2 -Wall -DLOAD_FUSE_ANIM_OLD=1 tests/load/fuse385/host.c -o "$OUT/old"
"$OUT/new" > "$OUT/new.txt"
if "$OUT/old" > "$OUT/old.txt"; then echo 'FAIL OLD not caught'; exit 1; else r=$?; fi
[ "$r" = 1 ]
grep -q 'FAIL flame frozen during slow read' "$OUT/old.txt"
grep -q 'PASS owner/disabled/fallback/short/EOF/error/drain' "$OUT/old.txt"
cat "$OUT/new.txt" "$OUT/old.txt"
echo 'PASS NEW / actual LOAD_FUSE_ANIM_OLD rejected'
