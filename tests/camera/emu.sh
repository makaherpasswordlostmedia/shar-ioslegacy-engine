#!/bin/bash
# Правки Роба 40 и 27 в эмуляторе: камера пешком и за машиной не заходит в стены (город у школы, Kwik-E-Mart, дома
# Симпсонов; комната — дом Симпсонов там, где камеры комнаты нет). Сценарий tests/camera/scenario.txt через tools/smoke.sh
# (общая очередь tools/ppsspp_run.sh), разбор tests/camera/check.py.
#   tests/camera/emu.sh [DIR]              зелёный: глаз ни разу не за препятствием
#   tests/camera/emu.sh --negative [DIR]   красный контроль: тот же сценарий с «flag nocamwall» (без обхода стен) —
#                                          глаз за стеной должен найтись хотя бы в 3 сценах
set -u; cd "$(dirname "$0")/../.."
NEG=0; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; PY=.venv/bin/python; LOG=$(mktemp -d); SCN=tests/camera/scenario.txt
if [ $NEG = 1 ]; then SCN="$LOG/scenario_neg.txt"; { echo "flag nocamwall"; cat tests/camera/scenario.txt; } > "$SCN"; fi
SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" > "$LOG/smoke.txt" 2>&1
REP=$(sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p' "$LOG/smoke.txt")
[ -n "$REP" ] || { echo "нет отчёта smoke: $(head -1 "$LOG/smoke.txt")"; exit 1; }
echo "прогон: $REP"
if [ $NEG = 1 ]; then $PY tests/camera/check.py "$REP" --expect-red; exit $?; fi
$PY tests/camera/check.py "$REP"
