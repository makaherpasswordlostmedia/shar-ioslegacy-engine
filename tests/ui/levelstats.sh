#!/bin/bash
# Гейт LEVEL PROGRESS (LevelStats.scr) и конца уровня (LevelEnd.scr) в эмуляторе: tests/ui/levelstats_scenario.txt -> tests/ui/levelstats_check.py.
# Сначала КРАСНЫЙ: «flag uilevelendold» (прежняя вспышка 3 с вместо экрана конца уровня) обязан провалить сверку; потом ЗЕЛЁНЫЙ.
#   tests/ui/levelstats.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/); первая строка итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; T="$ROOT/build/gates/levelstats/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T"
run() { local log; log=$(SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$SRC" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
sed 's/^flag msn$/flag msn\nflag uilevelendold/' tests/ui/levelstats_scenario.txt > "$T/planted.txt"
R1=$(run "$T/planted.txt")
if "$PY" tests/ui/levelstats_check.py "$R1" > "$T/red.txt"; then echo "FAIL: прежний код прошёл сверку — проверка слепая"; exit 1; fi
echo "красный как надо: $(head -1 "$T/red.txt")"
R2=$(run "$ROOT/tests/ui/levelstats_scenario.txt"); "$PY" tests/ui/levelstats_check.py "$R2"; RC=$?
echo "прогон: ${R2#$ROOT/}"; exit $RC
