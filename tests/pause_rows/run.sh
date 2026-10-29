#!/bin/bash
# Гейт правки Роба 137 (RESET CAR в паузе — у оригинала нет): один прогон эмулятора tools/smoke.sh по tests/pause_rows/scenario.txt.
# Сначала КРАСНЫЙ: сверка с требованиями игрока на открытии паузы с «flag resetrowold» (прежний код) обязана упасть;
# потом ЗЕЛЁНЫЙ: игрок — строки нет и ↓ + X не RESET CAR, служебный режим — строка есть.
#   tests/pause_rows/run.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/); код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build}"; PY="$ROOT/.venv/bin/python"
LOG=$(SMOKE_SCN="$ROOT/tests/pause_rows/scenario.txt" tools/smoke.sh "$SRC" 2>&1)
REP="$ROOT/$(echo "$LOG" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
[ -f "$REP/smoke.txt" ] || { echo "FAIL: нет отчёта smoke: $(echo "$LOG" | head -2)"; exit 1; }
if "$PY" tests/pause_rows/check.py "$REP" --planted > "$REP/red.txt"; then echo "FAIL: прежний код прошёл сверку — проверка слепая"; exit 1; fi
echo "красный как надо: $(head -1 "$REP/red.txt")"
"$PY" tests/pause_rows/check.py "$REP"; RC=$?
echo "прогон: ${REP#$ROOT/}"; exit $RC
