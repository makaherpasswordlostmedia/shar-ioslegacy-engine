#!/bin/bash
# Камеры зон города в эмуляторе (правка Роба 40): сценарий tests/camera/zonecam_scenario.txt через tools/smoke.sh (общая очередь
# tools/ppsspp_run.sh), разбор tests/camera/zonecam_check.py emu.
#   tests/camera/zonecam_emu.sh [DIR]              зелёный: у двери дома Симпсонов снимает z1_cam1 из точки локатора
#   tests/camera/zonecam_emu.sh --negative [DIR]   красный: «flag zoneoff» (без камер зон, как до правки) — сверка обязана упасть
set -u; cd "$(dirname "$0")/../.."
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d); SCN=tests/camera/zonecam_scenario.txt
if [ $NEG = 1 ]; then SCN="$LOG/zonecam_neg.txt"; { echo "flag zoneoff"; cat tests/camera/zonecam_scenario.txt; } > "$SCN"; fi
SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
[ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; exit 1; }
echo "прогон: $REP ($(head -1 "$LOG/smoke.txt"))"
if [ $NEG = 1 ]; then $PY tests/camera/zonecam_check.py emu "$REP/smoke.txt" --expect-red; exit $?; fi
$PY tests/camera/zonecam_check.py emu "$REP/smoke.txt"
