#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
DATA="${1:-build/final-production-data}"
BANK="$DATA/audio/"
[ -d "$BANK" ] || BANK="$DATA/l1/audio/"
OUT="build/test_horn_stop"
mkdir -p "$OUT"

echo "=== Compiling NEW ==="
cc -O2 -std=c11 -DAUDIO_HOST -I viewer tests/traffic_horn/test_horn_stop.c -lm -o "$OUT/test_new"
if "$OUT/test_new" "$BANK"; then
  echo "NEW: PASS (honk stops on timer, despawn, and distance)"
else
  echo "NEW: FAIL"
  exit 1
fi

echo "=== Compiling OLD (Red Control) ==="
cc -O2 -std=c11 -DAUDIO_HOST -DHORN_STOP_OLD=1 -I viewer tests/traffic_horn/test_horn_stop.c -lm -o "$OUT/test_old"
if "$OUT/test_old" "$BANK"; then
  echo "RED CONTROL FAILED: OLD should fail (exit 1)"
  exit 1
else
  echo "RED CONTROL: PASS (OLD correctly reproduceed bug / returned error)"
fi

echo "ALL HORN TESTS PASSED!"
