#!/bin/bash
# Гейт правки Роба 106 (повтор 01.10: «швы, ещё больше полосы на дороге везде»; «не допускай, чтобы пересборка опять
# возвращала швы»). Мак, CPU, ~2 мин. Сначала КРАСНЫЙ, потом ЗЕЛЁНЫЙ:
#   1. tests/seams/origin24.py — центры кусков на решётке 2^-9 м (как до правки) в 24-бит матрице GE: щели на дороге —
#      обязан упасть; по правилу ORIGIN_STEP 1/16 м — 0 щелей
#   2. tests/seams/skirts.py — юбки (выключены по умолчанию, SHR_SKIRTS=1): без юбок и «без близнеца» — обязан упасть
#   3. сторож tools/ship.sh (tools/seams_raster.py --gate, эталон tools/seams_ref.tsv): уровень до правки (OLD) и
#      подложенная сборка со щелями (--plant из NEW) — FAIL; новая сборка (NEW) — OK
# Запуск: tests/seams/run.sh [NEW.shr] [OLD.shr]   (по умолчанию build/level_seams.shr и build/level.shr)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; NEW=${1:-build/level_seams.shr}; OLD=${2:-build/level.shr}; OUT=build/tmp_conv/seams_gate; mkdir -p "$OUT"
red=0; green=0
must_fail() { local what=$1; shift; if "$@" > "$OUT/r.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: $what — $(tail -1 "$OUT/r.txt")"
  else echo "красный ($what): упал, как должен — $(tail -1 "$OUT/r.txt" | cut -c1-150)"; red=$((red + 1)); fi; }
must_pass() { local what=$1; shift; if "$@" > "$OUT/g.txt" 2>&1; then echo "зелёный ($what): $(tail -1 "$OUT/g.txt" | cut -c1-150)"; green=$((green + 1))
  else echo "ЗЕЛЁНЫЙ УПАЛ: $what — $(tail -1 "$OUT/g.txt")"; fi; }
must_fail "центры на решётке 2^-9" $PY tests/seams/origin24.py --rule grid
must_pass "центры ORIGIN_STEP" $PY tests/seams/origin24.py
must_fail "без юбок" $PY tests/seams/skirts.py --rule none
must_fail "юбки без близнеца" $PY tests/seams/skirts.py --rule notwin
must_pass "юбки по правилу" $PY tests/seams/skirts.py
[ -f "$NEW" ] && [ -f "$OLD" ] || { echo "FAIL: нет $NEW или $OLD"; exit 1; }
must_fail "уровень до правки $OLD" $PY tools/seams_raster.py "$OLD" --gate
$PY tools/seams_raster.py --plant "$NEW" "$OUT/planted.shr" > /dev/null || { echo "FAIL: --plant"; exit 1; }
must_fail "подложенная сборка со щелями" $PY tools/seams_raster.py "$OUT/planted.shr" --gate
rm -f "$OUT/planted.shr"
must_pass "новая сборка $NEW" $PY tools/seams_raster.py "$NEW" --gate
if [ $red -eq 5 ] && [ $green -eq 3 ]; then echo "PASS: красный 5/5 пойман, зелёный 3/3"; exit 0; fi
echo "FAIL: красный $red/5, зелёный $green/3"; exit 1
