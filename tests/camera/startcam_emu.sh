#!/bin/bash
# Камеры старта фаз миссий в эмуляторе (правка Роба 40): сценарий tests/camera/startcam_scenario.txt через tools/smoke.sh
# (общая очередь tools/ppsspp_run.sh), разбор tests/camera/startcam_check.py.
#   tests/camera/startcam_emu.sh [DIR]                 зелёный: m0sd..m7sd с крючка миссий, как на диске, игрок стоит
#   tests/camera/startcam_emu.sh --negative rev [DIR]  красный: камера задом наперёд (flag msncamplant 1) — сверка обязана упасть
#   tests/camera/startcam_emu.sh --negative off [DIR]  красный: камера со сдвигом 20 м (flag msncamplant 2)
# Красные — короткий сценарий (m0sd и m1sd), чтобы окно эмулятора стояло недолго.
set -u; cd "$(dirname "$0")/../.."
NEG=""; if [ "${1:-}" = --negative ]; then NEG="$2"; shift 2; fi
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d); SCN=tests/camera/startcam_scenario.txt
if [ -n "$NEG" ]; then
  N=1; [ "$NEG" = off ] && N=2
  SCN="$LOG/startcam_$NEG.txt"
  awk -v n=$N '/^flag msn$/ { print "flag msncamplant " n } { print } /^shot start_m1sd/ { exit }' tests/camera/startcam_scenario.txt > "$SCN"
  echo "wait 3.5" >> "$SCN"; echo "end" >> "$SCN"
fi
SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
[ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; exit 1; }
echo "прогон: $REP ($(head -1 "$LOG/smoke.txt"))"
if [ -n "$NEG" ]; then   # короткий сценарий: сверка только по m0sd и m1sd — упасть обязана из-за подложенной камеры
  $PY tests/camera/startcam_check.py "$REP/smoke.txt" --phases m0sd,m1sd --expect-red; exit $?
fi
$PY tests/camera/startcam_check.py "$REP/smoke.txt"
