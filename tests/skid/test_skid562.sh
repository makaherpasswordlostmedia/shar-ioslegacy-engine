#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
DATA="${1:-build/final-production-data}"
BANK="$DATA/audio/"
[ -d "$BANK" ] || BANK="$DATA/l1/audio/"
OUT="build/test_skid562"
mkdir -p "$OUT"

echo "=== Compiling NEW ==="
cc -O2 -std=c11 -DAUDIO_HOST -DSKID_HOST -I viewer tests/skid/test_skid562.c viewer/skid.c viewer/car.c viewer/col.c -lm -o "$OUT/test_new"
if "$OUT/test_new" "$BANK"; then
  echo "NEW: PASS (no skid sound standing still, scaled volume at speed)"
else
  echo "NEW: FAIL"
  exit 1
fi

echo "=== Compiling OLD (Red Control) ==="
cc -O2 -std=c11 -DAUDIO_HOST -DSKID_HOST -DSKID_OLD=1 -I viewer tests/skid/test_skid562.c viewer/skid.c viewer/car.c viewer/col.c -lm -o "$OUT/test_old"
if "$OUT/test_old" "$BANK"; then
  echo "RED CONTROL FAILED: OLD should fail (exit 1)"
  exit 1
else
  echo "RED CONTROL: PASS (OLD correctly reproduced bug / returned error)"
fi

echo "ALL SKID TESTS PASSED!"
