#!/bin/bash
# Native resources, measured start cadence, actual OLD red. All attempts retained.
ulimit -n 65536
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
mkdir -p build/gates/bonus_screens
OUT=$(mktemp -d "$ROOT/build/gates/bonus_screens/gate-XXXXXX")
EB="${1:-build/codex6-bonus-sdk/EBOOT.PBP}"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
"$PY" tools/bonus/screens_export.py > "$OUT/export.txt" 2>&1
"$PY" tools/bonus/screens_export.py --check build/bonus/mini.shr > "$OUT/source-green.txt" 2>&1
if BONUS_UI_STRETCH=1 "$PY" tools/bonus/screens_export.py --check build/bonus/mini.shr > "$OUT/source-red.txt" 2>&1; then
  echo "FAIL actual stretched exporter was accepted"; exit 1
fi
"$PY" tools/bonus/flyby_export.py --out "$OUT/fresh.cam" > "$OUT/flyby.txt" 2>&1
cmp build/bonus/flyby.cam "$OUT/fresh.cam"
RED="${BONUS_OLD_EBOOT:-}"
if [ -z "$RED" ]; then
 psp-cmake -S viewer -B "$OUT/old-sdk" -DCMAKE_C_FLAGS="-DBONUS_SCREENS_OLD=1 -DBONUS_COUNT_PS2_OLD=1 -DBONUS_SETUP_PS2_OLD=1" > "$OUT/old-config.txt" 2>&1
 cmake --build "$OUT/old-sdk" -j4 > "$OUT/old-build.txt" 2>&1
 RED="$OUT/old-sdk/EBOOT.PBP"
fi
"$PY" tests/bonus/screens_native.py "$EB" > "$OUT/native-green.txt" 2>&1
"$PY" tests/bonus/screens_native.py "$RED" --red > "$OUT/native-red.txt" 2>&1
cat "$OUT/source-green.txt" "$OUT/native-green.txt" "$OUT/native-red.txt"
echo "PASS screens; artifacts $OUT"
