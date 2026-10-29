#!/bin/bash
# Гейт подсказок обучения Барта (Tutorial.scr, viewer/tutorial.c) в эмуляторе: tests/ui/tutorial_scenario.txt -> tests/ui/tutorial_check.py.
# Сначала КРАСНЫЙ: копия набора с ui.shr без экрана подсказок (UI_NO_TUTORIAL=1 tools/ui_export.py — как прежний пакет) обязана
# провалить сверку; --layout — ещё красный по раскладке: шрифт подсказок в натуральную величину (UI_TUT_GLYPH_K=1) — строки шире
# рамки. Потом ЗЕЛЁНЫЙ.
#   tests/ui/tutorial.sh [--layout] [DIR]   DIR — EBOOT + данные (по умолчанию build/); первая строка итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
LAYOUT=0; [ "${1:-}" = --layout ] && { LAYOUT=1; shift; }
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; SCN="$ROOT/tests/ui/tutorial_scenario.txt"; T="$ROOT/build/gates/tutorial/$(date +%Y%m%d-%H%M%S)"
export SHR_TMP="${SHR_TMP:-$T/tmp_conv}"; mkdir -p "$SHR_TMP"
run() { local log; log=$(SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$1" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
red() {   # $1 — имя, $2 — переменная подброски для tools/ui_export.py
  mkdir -p "$T/$1"
  for f in "$SRC"/*; do [ "$(basename "$f")" = ui.shr ] || ln -s "$f" "$T/$1/$(basename "$f")"; done
  env "$2" "$PY" tools/ui_export.py --out "$T/$1/ui.shr" > "$T/$1.export.txt" 2>&1 || { echo "FAIL: подброска $2 не собралась"; exit 1; }
  local R; R=$(run "$T/$1")
  if "$PY" tests/ui/tutorial_check.py "$R" > "$T/$1.txt"; then echo "FAIL: подброска $2 прошла сверку — проверка слепая"; exit 1; fi
  echo "красный как надо ($2): $(head -1 "$T/$1.txt")"
}
red notut UI_NO_TUTORIAL=1
[ $LAYOUT = 1 ] && red bigfont UI_TUT_GLYPH_K=1.0
R2=$(run "$SRC"); "$PY" tests/ui/tutorial_check.py "$R2"; RC=$?
echo "прогон: ${R2#$ROOT/}"; exit $RC
