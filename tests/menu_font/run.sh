#!/bin/bash
# Гейт правки Роба 136 (шрифт главного меню — пиксель-перфект под PSP): tests/ui/menu_font_check.py по build/ui.shr, Мак, CPU.
# Сначала КРАСНЫЙ — прежняя дробная грань boulder_24*1.35 (UI_MENU_SOFT=1 tools/ui_export.py pack) обязана упасть,
# потом ЗЕЛЁНЫЙ — грань диска 1:1 (MENU_FACE). Зелёный пак пишется последним: build/ui.shr и build/ui/layout.json — новые.
# UI_MENU_FACE=boulder_24@1 bash tests/menu_font/run.sh — тот же гейт для крупного варианта. Итог: build/menu_font/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/menu_font; mkdir -p "$OUT"
UI_MENU_SOFT=1 "$PY" tools/ui_export.py pack > "$OUT/red_pack.txt" 2>&1 || { echo "FAIL: красный пак не собрался"; exit 1; }
"$PY" tests/ui/menu_font_check.py > "$OUT/red.txt" 2>&1; rc=$?
if [ $rc -ne 0 ] && grep -q "масштаб не целый\|не как на диске" "$OUT/red.txt"; then echo "красный (UI_MENU_SOFT=1, boulder_24*1.35): упал, как должен"; red=1
else echo "КРАСНЫЙ НЕ ПОЙМАН (rc=$rc)"; red=0; fi
"$PY" tools/ui_export.py pack > "$OUT/green_pack.txt" 2>&1 || { echo "FAIL: пак не собрался"; exit 1; }
"$PY" tests/ui/menu_font_check.py > "$OUT/green.txt" 2>&1; rc=$?
tail -2 "$OUT/green.txt"
if [ $red -eq 1 ] && [ $rc -eq 0 ]; then echo "PASS: красный 1/1 пойман, зелёный — буквы меню 1:1 с диска"; exit 0; fi
echo "FAIL: красный $red/1, зелёный rc=$rc"; exit 1
