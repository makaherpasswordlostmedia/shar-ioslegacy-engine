#!/bin/bash
# Native pickup/trap gate. Full copies and every attempt retained.
ulimit -n 65536
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
mkdir -p build/gates/bonus_pickups
OUT=$(mktemp -d "$ROOT/build/gates/bonus_pickups/gate-XXXXXX")
EB="${1:-build/codex6-bonus-pickups-sdk/EBOOT.PBP}"
export BONUS_STAGE="${2:-$ROOT/build/bonus-pickups-stage}"
export PSPDEV="$ROOT/pspdev" PATH="$ROOT/pspdev/bin:$PATH"
RED="${BONUS_OLD_EBOOT:-}"
if [ -z "$RED" ]; then
 psp-cmake -S viewer -B "$OUT/old-sdk" -DCMAKE_C_FLAGS=-DBONUS_PICKUPS_OLD=1 > "$OUT/config.log" 2>&1
 cmake --build "$OUT/old-sdk" -j4 > "$OUT/build.log" 2>&1
 RED="$OUT/old-sdk/EBOOT.PBP"
fi
"$PY" tests/bonus/pickups_native.py "$EB" > "$OUT/green.txt" 2>&1
"$PY" tests/bonus/pickups_native.py "$RED" --red > "$OUT/red.txt" 2>&1
cat "$OUT/green.txt" "$OUT/red.txt"
echo "PASS pickups native; artifacts $OUT"
