#!/bin/bash
# Гейт правки 411: tests/fartint/run.sh [red] [STAGE]  (STAGE — папка с EBOOT и данными 7 уровней, по умолчанию build/ship_stage)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; S=scenario.txt; [ "${1:-}" = red ] && { S=scenario_red.txt; shift; }
STAGE=${1:-$ROOT/build/ship_stage}
LOG=$(mktemp); SHIP_LEVELS="2 3 4 5 6 7" SMOKE_HEADLESS=1 SMOKE_MAXT=1300 SMOKE_SCN="$ROOT/tests/fartint/$S" "$ROOT/tools/smoke.sh" "$STAGE" > "$LOG" 2>&1
OUT=$(grep -o 'build/smoke/[0-9-]*' "$LOG" | tail -1); rm -f "$LOG"
echo "прогон: $OUT"; "$ROOT/.venv/bin/python" "$ROOT/tests/fartint/gate.py" "$ROOT/$OUT" --json "$ROOT/$OUT/fartint.json"
