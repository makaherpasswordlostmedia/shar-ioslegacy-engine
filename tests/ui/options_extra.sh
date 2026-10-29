#!/bin/bash
# Гейт OPTIONS главного меню: VIEW CREDITS и VIEW MOVIES (menu.shr экраны 2, 3; viewer/main.c optionsRun) в эмуляторе:
# tests/ui/options_extra_scenario.txt -> tests/ui/options_extra_check.py.
# Сначала КРАСНЫЙ: копия набора с menu.shr как до 29.09 (MENU_OLD=1 tools/menu_export.py: только options и sound) обязана
# провалить сверку; потом ЗЕЛЁНЫЙ.
#   tests/ui/options_extra.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/); первая строка итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; SCN="$ROOT/tests/ui/options_extra_scenario.txt"; T="$ROOT/build/gates/options_extra/$(date +%Y%m%d-%H%M%S)"
export SHR_TMP="${SHR_TMP:-$T/tmp_conv}"; mkdir -p "$SHR_TMP" "$T/old"
run() { local log; log=$(SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$1" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
for f in "$SRC"/*; do [ "$(basename "$f")" = menu.shr ] || ln -s "$f" "$T/old/$(basename "$f")"; done
MENU_OLD=1 "$PY" tools/menu_export.py --pack menu --out "$T/old/menu.shr" > "$T/old.export.txt" 2>&1 || { echo "FAIL: подброска MENU_OLD не собралась"; exit 1; }
R1=$(run "$T/old")
if "$PY" tests/ui/options_extra_check.py "$R1" > "$T/red.txt"; then echo "FAIL: menu.shr без титров и роликов прошёл сверку — проверка слепая"; exit 1; fi
echo "красный как надо: $(head -1 "$T/red.txt")"
R2=$(run "$SRC"); "$PY" tests/ui/options_extra_check.py "$R2"; RC=$?
echo "прогон: ${R2#$ROOT/}"; exit $RC
