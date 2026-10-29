#!/bin/bash
# Гейт №912 «Мультик без текстур» (безголовый эмулятор, своя папка эмулятора):
#   tests/toon/flat912.sh EBOOT.PBP НАБОР [ВЫХОД]
# НАБОР — папка данных с level.shr, notoon.txt, flat912.bin, marks912.bin (L1 в корне). Сценарий tests/toon/flat912_scenario.txt: те же виды с заливкой и с текстурами (flag flat912 1/0).
# Проверки (tests/toon/flat912_check.py): 1) движок прочёл flat912.bin и marks912.bin (FLATLIST ok=1, MARKSLIST ok=1); 2) заливка меняет картинку (красный контроль: отличие > 1 % пикселей),
# но средний цвет кадра тот же (±10 из 255); 3) дыр не больше, чем с текстурами (clearchk + кадр без неба: непокрытые пиксели пурпурные); 4) сценарий дошёл до END.
# №918: слой нарисованной разметки выключен по умолчанию, поэтому marks912.bin проверяется только с FLAT912_MARKS=1 (в сценарий добавляется «flag marks918old 1»)
set -u
cd "$(dirname "$0")/../.."; ROOT=$PWD
EB=${1:?EBOOT.PBP}; PK=${2:?НАБОР}; OUT=${3:-$ROOT/build/flat912_gate/$(date +%H%M%S)}
mkdir -p "$OUT"; TMP="$ROOT/build/flat912_pkg_$$"; trap 'rm -rf "$TMP"' EXIT
cp -cR "$PK" "$TMP" 2>/dev/null || cp -R "$PK" "$TMP"; cp "$EB" "$TMP/EBOOT.PBP"
SCN="$ROOT/tests/toon/flat912_scenario.txt"
if [ -n "${FLAT912_MARKS:-}" ]; then SCN="$OUT/scenario_marks.txt"; awk '{print} /^scene S_L1/ && !d {print "flag marks918old 1"; d=1}' "$ROOT/tests/toon/flat912_scenario.txt" > "$SCN"; fi   # №918: слой нарисованной разметки (MARKS918_OLD) — проверка чтения marks912.bin только так
EXTRA="notoon.txt flat912.bin marks912.bin"
( SMOKE_HOME="$OUT/home" SMOKE_EXTRA="$EXTRA" SMOKE_OPTS=2017f SMOKE_FLAGS="clearchk${FLAT912_RED:+ flat912old}" SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN="$SCN" SMOKE_MAXT=500 nice tools/smoke.sh "$TMP" ) > "$OUT/smoke.out" 2>&1
D="$ROOT/$(grep -o "build/smoke/[0-9-]*" "$OUT/smoke.out" | head -1)"; [ -d "$D" ] || { echo "FAIL нет папки прогона смоука"; exit 2; }; rm -rf "$OUT/run"; cp -R "$D" "$OUT/run"   # папка из строки «отчёт:» самого прогона (параллельные прогоны не путаются)
python3 "$ROOT/tests/toon/flat912_check.py" "$OUT/run"; RC=$?
# красный контроль: FLAT912_RED=1 кладёт рядом с EBOOT файл flat912old — заливка выключена, проверка обязана упасть (иначе гейт ничего не ловит)
if [ -n "${FLAT912_RED:-}" ]; then if [ $RC -ne 0 ]; then echo "КРАСНЫЙ КОНТРОЛЬ: упал, как должен"; exit 0; else echo "КРАСНЫЙ КОНТРОЛЬ: гейт не упал с выключенной заливкой"; exit 1; fi; fi
exit $RC
