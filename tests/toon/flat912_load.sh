#!/bin/bash
# Гейт №912 п.А «Мультик не нагружает кадры после загрузки уровня» (безголовый эмулятор, своя папка эмулятора):
#   tests/toon/flat912_load.sh EBOOT.PBP НАБОР [ВЫХОД]
# НАБОР — как у flat912.sh. Сценарий tests/toon/flat912_load_scenario.txt: L1 → L4 → L5 с настройками по умолчанию (Cartoon, заливка).
# Красный контроль: FLAT912_RED=1 включает прежнее поведение (FLAT912_RED=rebuild — только А без пересборки после смены уровня) (строки «flag flatrescanold 1 / flatdump 1 / flatrebuildold 1» в начале сценария: файлы-флаги в релизной сборке закрыты shrDevName) — гейт обязан упасть.
set -u
cd "$(dirname "$0")/../.."; ROOT=$PWD
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; OUT=${3:-$ROOT/build/flat912_load_gate/$(date +%H%M%S)}
mkdir -p "$OUT"; TMP="$ROOT/build/flat912_load_pkg_$$"; trap 'rm -rf "$TMP"' EXIT
cp -cR "$PK" "$TMP" 2>/dev/null || cp -R "$PK" "$TMP"; cp "$EB" "$TMP/EBOOT.PBP"
SCN="$ROOT/tests/toon/flat912_load_scenario.txt"
if [ -n "${FLAT912_RED:-}" ]; then SCN="$OUT/scenario_red.txt"; awk -v R="$FLAT912_RED" '{print} /^scene F_L1/ && !d {if (R != "rebuild") { print "flag flatrescanold 1"; print "flag flatdump 1" } print "flag flatrebuildold 1"; d=1}' "$ROOT/tests/toon/flat912_load_scenario.txt" > "$SCN"; fi
EXTRA="notoon.txt flat912.bin marks912.bin"; for n in 2 3 4 5 6 7; do EXTRA="$EXTRA l$n/notoon.txt l$n/flat912.bin l$n/marks912.bin"; done
# красный контроль гоняет сценарий дважды и считается красным, если упал хотя бы один прогон (ошибка цвета зависит от порядка готовности данных: в 1 прогоне из 4 красный проходил, L5 529 пикселей)
NRUN=1; [ -n "${FLAT912_RED:-}" ] && NRUN=2
RC=0; REDHIT=0; INCOMPLETE=0
for k in $(seq 1 $NRUN); do
  ( SMOKE_HOME="$OUT/home$k" SMOKE_EXTRA="$EXTRA" SHIP_LEVELS="2 3 4 5 6 7" SMOKE_FLAGS="" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$SCN" SMOKE_MAXT=500 tools/smoke.sh "$TMP" > "$OUT/smoke$k.out" 2>&1 )
  D="$ROOT/$(grep -o "build/smoke/[0-9-]*" "$OUT/smoke$k.out" | head -1)"; [ -d "$D" ] || { echo "FAIL нет папки прогона смоука"; exit 2; }; rm -rf "$OUT/run$k"; cp -R "$D" "$OUT/run$k"
  echo "--- прогон $k из $NRUN"; python3 "$ROOT/tests/toon/flat912_load_check.py" "$OUT/run$k" | tee "$OUT/check$k.txt"; r=${PIPESTATUS[0]}
  if grep -q "нет строки END" "$OUT/check$k.txt"; then INCOMPLETE=$((INCOMPLETE + 1)); echo "прогон $k не дошёл до END (машина занята?) — в красный контроль не засчитан"; continue; fi   # упал по таймауту, а не по делу
  if [ $r -ne 0 ]; then REDHIT=1; RC=$r; fi
done
if [ $INCOMPLETE -ge $NRUN ]; then echo "FAIL ни один прогон не дошёл до END"; exit 2; fi
if [ -n "${FLAT912_RED:-}" ]; then if [ $REDHIT -ne 0 ]; then echo "КРАСНЫЙ КОНТРОЛЬ: упал (хотя бы один из $NRUN прогонов), как должен"; exit 0; else echo "КРАСНЫЙ КОНТРОЛЬ: гейт не упал ни в одном из $NRUN прогонов с прежним поведением"; exit 1; fi; fi
exit $RC
