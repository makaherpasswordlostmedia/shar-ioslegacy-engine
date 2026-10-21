#!/bin/bash
# Гейт радара (правка Роба 50): tests/ui/radar_scenario.txt через tools/smoke.sh, разбор tests/ui/radar_check.py.
#   tests/ui/radar_emu.sh [DIR]              зелёный: клин от центра к цели, цель за краем — на ободе, у обода только цели
#   tests/ui/radar_emu.sh --negative [DIR]   красный: flag coneoff (клин вверх всегда, все значки у обода — как до правки)
set -u; cd "$(dirname "$0")/../.."
NEG=""; [ "${1:-}" = --negative ] && { NEG=1; shift; }
SRC="${1:-build}"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; SCN=tests/ui/radar_scenario.txt
if [ -n "$NEG" ]; then sed 's/^flag radarlog$/flag radarlog\nflag coneoff/' "$SCN" > "$T/s.txt"; SCN="$T/s.txt"; fi
L=$(SMOKE_SCN="$SCN" tools/smoke.sh "$SRC" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
[ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
echo "прогон: $R"
.venv/bin/python tests/ui/radar_check.py "$R" ${NEG:+--expect-red}
