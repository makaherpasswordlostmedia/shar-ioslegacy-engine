#!/bin/bash
# Fresh, owned headless runs; retained same-frame snapshots and an actual camera fault.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
DATA="${SCEN_ROOT:-$HOME/Downloads/shar-psp}"
TAG="${RF_TAG:-rf_$(date +%Y%m%d_%H%M%S)}"
OUT="$DATA/build/codex-terminal/f4/$TAG"
mkdir -p "$OUT"
export SCEN_EBOOT="${1:-$ROOT/viewer/build/EBOOT.PBP}"
export SCEN_HOME="$OUT/home"
PY="$ROOT/.venv/bin/python"
SCEN=$HOME/.claude/skills/shar-level-polish/scripts/scen.py
"$PY" "$SCEN" "${TAG}_green" "$ROOT/tests/render/ab_scenario.txt" > "$OUT/run-green.log" 2>&1
"$PY" tests/render/frozen.py "$DATA/build/twins/scen/full/${TAG}_green" --out "$OUT/green"
{ printf 'flag rfbreak 1\n'; cat tests/render/ab_scenario.txt; } > "$OUT/broken.txt"
export SCEN_HOME="$OUT/red-home"
"$PY" "$SCEN" "${TAG}_red" "$OUT/broken.txt" > "$OUT/run-red.log" 2>&1
if "$PY" tests/render/frozen.py "$DATA/build/twins/scen/full/${TAG}_red" --out "$OUT/red" > "$OUT/negative.txt"; then
  echo 'FAIL: actual camera fault not detected'; exit 1
fi
# Missing runs/data must not masquerade as a successful negative control.
rg -q 'changed hash|changed eye' "$OUT/negative.txt"
rg -q 'differs in [1-9][0-9]* pixels' "$OUT/negative.txt"
echo "PASS frozen frame and actual camera negative; evidence $OUT"
