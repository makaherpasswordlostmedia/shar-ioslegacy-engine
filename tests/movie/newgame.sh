#!/bin/bash
# Гейт ролика новой игры fmv1a в эмуляторе (tests/movie/newgame_scenario.txt -> tests/movie/newgame_check.py).
# Сначала КРАСНЫЙ: копия набора с обрезанным movies/fmv1a.smv (первые 64 КБ — ролик битый) — сверка обязана упасть; потом ЗЕЛЁНЫЙ.
#   tests/movie/newgame.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/); первая строка итог, код 0 = OK
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
[ -f "$SRC/EBOOT.PBP" ] && [ -f "$SRC/movies/fmv1a.smv" ] || { echo "FAIL: в $SRC нет EBOOT.PBP / movies/fmv1a.smv"; exit 1; }
PY="$ROOT/.venv/bin/python"; SCN="$ROOT/tests/movie/newgame_scenario.txt"
run() { local log; log=$(SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$1" 2>&1); echo "$ROOT/$(echo "$log" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"; }
T="$ROOT/build/gates/newgame_fmv/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$T/set/movies"
for f in "$SRC"/*; do [ "$(basename "$f")" = movies ] || ln -s "$f" "$T/set/$(basename "$f")"; done
for f in "$SRC"/movies/*; do ln -s "$f" "$T/set/movies/$(basename "$f")"; done
rm "$T/set/movies/fmv1a.smv"; head -c 65536 "$SRC/movies/fmv1a.smv" > "$T/set/movies/fmv1a.smv"
R1=$(run "$T/set")
if "$PY" tests/movie/newgame_check.py "$R1" > "$T/red.txt"; then echo "FAIL: битый fmv1a.smv прошёл сверку — проверка слепая"; exit 1; fi
echo "красный как надо: $(head -1 "$T/red.txt")"
R2=$(run "$SRC"); "$PY" tests/movie/newgame_check.py "$R2"; RC=$?
echo "прогон: ${R2#$ROOT/}"; exit $RC
