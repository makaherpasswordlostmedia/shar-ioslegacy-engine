#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
DATA="${1:-build/final-production-data}"
BANK="$DATA/audio/"
[ -d "$BANK" ] || BANK="$DATA/l1/audio/"
[ -d "$BANK" ] || BANK="../shar-psp-sonnet-runs-w/build/final-work/l1/audio/"
[ -d "$BANK" ] || BANK="../shar-psp-sonnet-runs-w/build/final-20261011-1721/audio/"
OUT="build/test_resume560"
mkdir -p "$OUT"

echo "Using audio bank: $BANK"

echo "=== Compiling NEW ==="
cc -O2 -std=c11 -DAUDIO_HOST -I viewer tests/audio/test_resume560.c viewer/audio.c -lm -o "$OUT/test_new"
if "$OUT/test_new" "$BANK"; then
  echo "NEW: PASS (music successfully continues streaming after sleep/resume)"
else
  echo "NEW: FAIL"
  exit 1
fi

echo "=== Compiling OLD (Red Control) ==="
cc -O2 -std=c11 -DAUDIO_HOST -DRESUME_AUDIO_OLD=1 -I viewer tests/audio/test_resume560.c viewer/audio.c -lm -o "$OUT/test_old"
if "$OUT/test_old" "$BANK"; then
  echo "RED CONTROL FAILED: OLD should fail (exit 1)"
  exit 1
else
  echo "RED CONTROL: PASS (OLD correctly reproduced bug: music died after sleep)"
fi

echo "ALL AUDIO RESUME TESTS PASSED!"
