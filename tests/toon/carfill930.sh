#!/bin/bash
# Гейт №930 (ступень 2): tests/toon/carfill930.sh EBOOT.PBP ИМЯ [OUT]   (данные — OVL=папка с carflat930.bin / carflatm930.bin по уровням, набор — SET как у tools/emu_run.sh)
# Прогоняет сценарий carfill930_scenario.txt (L1, машина трафика стоит, свободная камера) в безголовом эмуляторе и проверяет его (carfill930_check.py): PASS / FAIL последней строкой.
# Красный контроль — EBOOT, собранный с -DCARFILL930_OLD=1 (заливка выключена совсем): гейт обязан упасть; второй красный — FLAT930_RED=1 (то же включено, но в окне G_ON выключено флагом carfill930 0)
set -u
cd "$(dirname "$0")/../.."; ROOT=$PWD
EB=${1:?EBOOT.PBP}; NAME=${2:?ИМЯ}; OUT=${3:-$ROOT/build/mult/gate_$NAME}; mkdir -p "$OUT"
SCN="$ROOT/tests/toon/carfill930_scenario.txt"
if [ "${FLAT930_RED:-}" = 1 ]; then SCN="$OUT/scenario_red.txt"; awk '/^flag carfill930 1/ && !d {print "flag carfill930 0"; d=1; next} {print}' "$ROOT/tests/toon/carfill930_scenario.txt" > "$SCN"; fi
OUT="$OUT" tools/emu_run.sh "$SCN" "$NAME" "$EB" 420 > "$OUT/run_$NAME.log" 2>&1; tail -1 "$OUT/run_$NAME.log"
python3 "$ROOT/tests/toon/carfill930_check.py" "$OUT/out_$NAME"
