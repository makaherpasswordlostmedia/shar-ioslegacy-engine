#!/bin/bash
# Гейт правок Роба 224/237/251 («опять много швов», «швов стало больше», «швы очень мигают»; слово Роба 03.10: лучше «прыгающие»
# полигоны, как на первой PlayStation, чем разрывы и просветы). Щели кадра PSP на модели GE float24 (tools/seams_ge.py: 12 видов
# tools/seams_scenario.txt × 3 кадра), Мак, CPU, ~2 мин. Эмулятор эти щели не показывает (PPSSPP считает вершины во float32).
# Сначала КРАСНЫЙ, потом ЗЕЛЁНЫЙ:
#   1. tests/seams/one_matrix.py (без диска): свой центр у куска и движок до правки — при склейке матриц (cat) щели, обязан
#      упасть; только центр клетки или только оси камеры — тоже щели; правило целиком — 0
#   2. уровень OLD (до правки: SHR_SEAMS_OLD=1 или эталон build/seams/ref/level_pre_seams.shr) с движком до правки (--abs) — FAIL по cat и по sep
#   3. уровень NEW с движком до правки (--abs) — FAIL по cat: клетка без осей камеры не закрывает стыки клеток
#   4. уровень NEW с движком в осях камеры (viewer/main.c) — OK по cat и по sep: щелей не больше SEAMS_GE_MAX (200; 03.10: 145 и 106 против 902 и 570 до правки)
# Запуск: tests/seams/ge.sh NEW.shr OLD.shr
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
# по умолчанию (сведение 03.10, проверка: после выпуска build/level.shr уже новый, и красный sep не ловится): NEW — выпуск,
# OLD — эталон до правки build/seams/ref/level_pre_seams.shr (2c8dca2f, сохранён при сведении; правило проекта build/<гейт>/ref)
PY=.venv/bin/python; NEW=${1:-build/level.shr}; OLD=${2:-build/seams/ref/level_pre_seams.shr}; OUT=build/tmp_conv/seams_ge_gate; mkdir -p "$OUT"
red=0; green=0
must_fail() { local what=$1; shift; if "$@" > "$OUT/r.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: $what — $(tail -1 "$OUT/r.txt")"
  else echo "красный ($what): упал, как должен — $(tail -1 "$OUT/r.txt" | cut -c1-160)"; red=$((red + 1)); fi; }
must_pass() { local what=$1; shift; if "$@" > "$OUT/g.txt" 2>&1; then echo "зелёный ($what): $(tail -1 "$OUT/g.txt" | cut -c1-160)"; green=$((green + 1))
  else echo "ЗЕЛЁНЫЙ УПАЛ: $what — $(tail -1 "$OUT/g.txt")"; fi; }
must_fail "синтетика: свой центр у куска, движок до правки" $PY tests/seams/one_matrix.py --rule piece --engine abs
must_fail "синтетика: только центр клетки" $PY tests/seams/one_matrix.py --rule cell --engine abs
must_fail "синтетика: только оси камеры" $PY tests/seams/one_matrix.py --rule piece --engine rel
must_pass "синтетика: правило (cat)" $PY tests/seams/one_matrix.py
must_pass "синтетика: правило (sep)" $PY tests/seams/one_matrix.py --ge sep
[ -f "$NEW" ] && [ -f "$OLD" ] || { echo "FAIL: нет $NEW или $OLD"; exit 1; }
must_fail "уровень до правки $OLD, движок до правки, cat" $PY tools/seams_ge.py "$OLD" --abs --ge cat --gate
must_fail "уровень до правки $OLD, движок до правки, sep" $PY tools/seams_ge.py "$OLD" --abs --ge sep --gate
must_fail "новый уровень, движок до правки, cat" $PY tools/seams_ge.py "$NEW" --abs --ge cat --gate
must_pass "новый уровень $NEW, движок в осях камеры, cat" $PY tools/seams_ge.py "$NEW" --ge cat --gate
must_pass "новый уровень $NEW, движок в осях камеры, sep" $PY tools/seams_ge.py "$NEW" --ge sep --gate
if [ $red -eq 6 ] && [ $green -eq 4 ]; then echo "PASS: красный 6/6 пойман, зелёный 4/4"; exit 0; fi
echo "FAIL: красный $red/6, зелёный $green/4"; exit 1
