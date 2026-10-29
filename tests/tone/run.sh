#!/bin/bash
# Гейт правки Роба 144 (насыщенность «чуть выше» + строка Colour в Settings паузы, viewer/tone.c).
# Хост (Мак, build/level.shr): tests/tone/host.c — сначала КРАСНЫЕ подброски (обязаны упасть):
#   -DTONE_INPLACE                    кривая поверх уже тонированной палитры (как palTone до 01.10): ползунок необратим
#   -DTONE_SAT_DEF=128 -DTONE_SOFT=0  прежняя насыщенность 1.28 с жёстким клампом: не «выше»
#   -DTONE_SOFT=0                     жёсткий кламп при 1.36: оттенок ярких цветов уезжает
# потом ЗЕЛЁНЫЙ. Эмулятор (--emu): tests/tone/scenario.txt -> check.py; КРАСНЫЙ — копия набора с pmenu.shr без строки
# (MENU_NO_COLOUR=1 tools/menu_export.py), потом ЗЕЛЁНЫЙ на DIR. Только через tools/smoke.sh (общая очередь эмулятора).
#   tests/tone/run.sh [--emu] [DIR]   DIR — EBOOT + данные (по умолчанию build/); код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EMU=0; [ "${1:-}" = --emu ] && { EMU=1; shift; }
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
PY="$ROOT/.venv/bin/python"; T="$ROOT/build/gates/tone/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T"
LV="$SRC/level.shr"; [ -f "$LV" ] || LV="$ROOT/build/level.shr"
hostrun() {   # $1 — имя, остальное — флаги компилятора
  local n=$1; shift
  cc -O1 -I viewer "$@" tests/tone/host.c viewer/tone.c -lm -o "$T/tone-$n" || { echo "FAIL: сборка tests/tone/host.c ($n)"; exit 1; }
  "$T/tone-$n" "$LV" > "$T/$n.txt"
}
for neg in "inplace:-DTONE_INPLACE" "old128:-DTONE_SAT_DEF=128 -DTONE_SOFT=0" "hard:-DTONE_SOFT=0"; do
  n=${neg%%:*}; fl=${neg#*:}
  # shellcheck disable=SC2086
  if hostrun "$n" $fl; then echo "FAIL: подброска $fl прошла — проверка слепая"; exit 1; fi
  echo "красный как надо ($fl): $(grep КРАСНОЕ "$T/$n.txt" | head -1)"
done
hostrun green -Wall || { cat "$T/green.txt"; echo "FAIL: хост"; exit 1; }
sed 's/^/  /' "$T/green.txt"
[ $EMU = 1 ] || { echo "PASS (хост; эмулятор — с ключом --emu)"; exit 0; }
run() { local log; log=$(SMOKE_SCN="$ROOT/tests/tone/scenario.txt" "$ROOT/tools/smoke.sh" "$1" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
mkdir -p "$T/nocolour"
for f in "$SRC"/*; do [ "$(basename "$f")" = pmenu.shr ] || ln -s "$f" "$T/nocolour/$(basename "$f")"; done
MENU_NO_COLOUR=1 "$PY" tools/menu_export.py --pack pmenu --out "$T/nocolour/pmenu.shr" > "$T/nocolour.export.txt" 2>&1 || { echo "FAIL: подброска pmenu без строки не собралась"; exit 1; }
R1=$(run "$T/nocolour")
if "$PY" tests/tone/check.py "$R1" > "$T/red_emu.txt"; then echo "FAIL: pmenu без строки Colour прошёл сверку — проверка слепая"; exit 1; fi
echo "красный как надо (pmenu без строки): $(head -1 "$T/red_emu.txt" | cut -c1-200)"
R2=$(run "$SRC"); "$PY" tests/tone/check.py "$R2"; RC=$?
echo "прогон: ${R2#$ROOT/}"; exit $RC
