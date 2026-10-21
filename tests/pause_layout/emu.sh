#!/bin/bash
# Снимки эмулятора до/после правок 150/151: один прогон tools/smoke.sh по tests/pause_layout/emu_scenario.txt на DIR.
#   tests/pause_layout/emu.sh DIR [SCN]   DIR — EBOOT.PBP + пакеты; которых нет — с места сборки (tools/smoke.sh); SCN — сценарий
#   (по умолчанию emu_scenario.txt: пауза миссии, OPTIONS, SOUND, SETTINGS, пауза свободной езды); печатает папку снимков
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SCN="$ROOT/tests/pause_layout/${2:-emu_scenario.txt}"
LOG=$(SMOKE_SCN="$SCN" tools/smoke.sh "${1:-$ROOT/build}" 2>&1)
REP="$(echo "$LOG" | sed -n 's/^отчёт: \(.*\)\/summary.txt.*/\1/p' | tail -1)"
echo "$LOG" | head -3; echo "снимки: $REP"
for s in $(awk '$1=="shot"{print $2}' "$SCN"); do
  [ -f "$ROOT/$REP/$s.png" ] || { echo "FAIL: нет снимка $s"; exit 1; }
done
