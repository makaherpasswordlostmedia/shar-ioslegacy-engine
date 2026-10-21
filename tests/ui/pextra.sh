#!/bin/bash
# Гейт экранов паузы VIEW CARDS и MISSION SELECT (pextra.shr) в эмуляторе: tests/ui/pextra_scenario.txt -> tests/ui/pextra_check.py.
# Сначала КРАСНЫЙ: копия набора без pextra.shr (VIEW CARDS выключен, MISSION SELECT — прежний текстовый список) обязана провалить
# сверку; потом ЗЕЛЁНЫЙ.
#   tests/ui/pextra.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/); первая строка итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; SCN="$ROOT/tests/ui/pextra_scenario.txt"; T="$ROOT/build/gates/pextra/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T/set"
run() { local log; log=$(SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$1" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
for f in "$SRC"/*; do [ "$(basename "$f")" = pextra.shr ] || ln -s "$f" "$T/set/$(basename "$f")"; done
: > "$T/set/pextra.shr"   # пустой файл: пакет не открывается (smoke.sh требует файл по списку поставки)
R1=$(run "$T/set")
if "$PY" tests/ui/pextra_check.py "$R1" > "$T/red.txt"; then echo "FAIL: набор без pextra.shr прошёл сверку — проверка слепая"; exit 1; fi
echo "красный как надо: $(head -1 "$T/red.txt")"
R2=$(run "$SRC"); "$PY" tests/ui/pextra_check.py "$R2"; RC=$?
echo "прогон: ${R2#$ROOT/}"; exit $RC
