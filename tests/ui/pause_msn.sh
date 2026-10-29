#!/bin/bash
# Гейт паузы миссии (PauseMission.scr) в эмуляторе: сценарий tests/ui/pause_msn_scenario.txt, сверка tests/ui/pause_msn_check.py.
# Сначала КРАСНЫЙ: «flag pauseold» (прежний код — в миссии пауза свободной езды) обязан провалить сверку; потом ЗЕЛЁНЫЙ.
#   tests/ui/pause_msn.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/); первая строка итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; T="$ROOT/build/gates/pause_msn/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T"
run() { local log; log=$(SMOKE_SCN="$1" "$ROOT/tools/smoke.sh" "$SRC" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
sed 's/^flag msn$/flag msn\nflag pauseold/' tests/ui/pause_msn_scenario.txt > "$T/planted.txt"
R1=$(run "$T/planted.txt")
if "$PY" tests/ui/pause_msn_check.py "$R1" > "$T/red.txt"; then echo "FAIL: прежний код прошёл сверку — проверка слепая"; exit 1; fi
echo "красный как надо: $(head -1 "$T/red.txt")"
R2=$(run "$ROOT/tests/ui/pause_msn_scenario.txt"); "$PY" tests/ui/pause_msn_check.py "$R2"; RC=$?
echo "прогон: ${R2#$ROOT/}"; exit $RC
