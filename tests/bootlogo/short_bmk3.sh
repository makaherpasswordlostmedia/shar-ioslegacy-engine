#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
OUT=build/bootlogo/short_bmk3
mkdir -p "$OUT"
cc -std=c99 -O0 -fsanitize=address -g -I viewer tests/bootlogo/short_bmk3.c -o "$OUT/new"
"$OUT/new" > "$OUT/new.txt" 2>&1
cc -std=c99 -O0 -fsanitize=address -g -DBOOTMARKS_SHORT_HEADER_OLD=1 -I viewer tests/bootlogo/short_bmk3.c -o "$OUT/old"
if "$OUT/old" > "$OUT/old.txt" 2>&1; then echo "FAIL: old short-header read survived"; exit 1; fi
grep -q 'ERROR: AddressSanitizer: heap-buffer-overflow' "$OUT/old.txt"
cat "$OUT/new.txt"
echo 'PASS: real OLD heap-buffer-overflow caught'
