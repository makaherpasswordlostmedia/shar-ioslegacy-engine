#!/bin/bash
# Гейт меню оригинала OPTIONS в эмуляторе: tools/options_scenario.txt через tools/smoke.sh, сверка tools/options_check.py.
#   tools/options_gate.sh [DIR]            DIR — EBOOT + данные (по умолчанию build/) -> первая строка итог, код 0 = OK
#   tools/options_gate.sh --negative [DIR] отрицательный контроль: копия набора с испорченным menu.shr (пакет не открывается,
#                                          экраны OPTIONS не появляются) — сверка обязана упасть (тогда PASS)
#   tools/options_gate.sh --mute [DIR]     отрицательный контроль звуков (29.09): «flag uisfx0» — звуки меню молчат, сверка обязана упасть
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NEG=0; MUTE=0; SCN="$ROOT/tools/options_scenario.txt"
[ "${1:-}" = --negative ] && { NEG=1; shift; }
if [ "${1:-}" = --mute ]; then NEG=1; MUTE=1; shift; mkdir -p "$ROOT/build/options_mute"; SCN="$ROOT/build/options_mute/scenario.txt"
  sed 's/^flag menu$/flag menu\nflag uisfx0/' "$ROOT/tools/options_scenario.txt" > "$SCN"; fi
SRC="${1:-$ROOT/build}"; case "$SRC" in /*) ;; *) SRC="$PWD/$SRC" ;; esac
if [ $NEG = 1 ] && [ $MUTE = 0 ]; then
  T="$ROOT/build/options_neg"; rm -rf "$T.old"; [ -d "$T" ] && mv "$T" "$T.old"; mkdir -p "$T"
  for f in "$SRC"/*; do ln -s "$f" "$T/$(basename "$f")"; done
  rm "$T/menu.shr"; head -c 4096 "$SRC/menu.shr" > "$T/menu.shr"; SRC="$T"
fi
LOG=$(SMOKE_SCN="$SCN" "$ROOT/tools/smoke.sh" "$SRC" 2>&1)
OUT="$ROOT/$(echo "$LOG" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
[ -f "$OUT/smoke.txt" ] || { echo "options_gate: смоук не отработал"; echo "$LOG" | head -5; exit 1; }
R=$(python3 "$ROOT/tools/options_check.py" "$OUT"); RC=$?
if [ $NEG = 1 ]; then
  if [ $RC != 0 ]; then echo "PASS (отрицательный контроль: сверка упала, как должна) — $R"; exit 0; fi
  echo "FAIL (отрицательный контроль прошёл сверку) — $R"; exit 1
fi
echo "$R"; echo "прогон: ${OUT#$ROOT/}"; exit $RC
