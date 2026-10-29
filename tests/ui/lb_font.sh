#!/bin/bash
# Гейт правки Роба 158 (подписи разговора «✕ Start Mission / △ Cancel», «✕ SKIP» — шрифтом PRESS START): экран letterbox
# в build/ui.shr — грань диска 1:1 (tests/ui/boot_font_check.py, как у правки 152). Сначала КРАСНЫЙ — прежняя дробная грань
# (UI_LB_FACE=boulder_16, т. е. boulder_16 x 272/480) обязана упасть, потом ЗЕЛЁНЫЙ — boulder_16@1; зелёный ui.shr — последним
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/lb_font; mkdir -p "$OUT"
UI_LB_FACE=boulder_16 "$PY" tools/ui_export.py > "$OUT/red_pack.txt" 2>&1 || { echo "FAIL: красный ui.shr не собрался"; exit 1; }
"$PY" tests/ui/boot_font_check.py --pack ui --screens letterbox --layout build/ui/layout.json > "$OUT/red.txt" 2>&1; rc=$?
red=0; if [ $rc -ne 0 ] && grep -q "масштаб не целый" "$OUT/red.txt"; then echo "красный (boulder_16 x 0.567): упал, как должен"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН (rc=$rc)"; fi
"$PY" tools/ui_export.py > "$OUT/green_pack.txt" 2>&1 || { echo "FAIL: ui.shr не собрался"; exit 1; }
"$PY" tests/ui/boot_font_check.py --pack ui --screens letterbox --layout build/ui/layout.json > "$OUT/green.txt" 2>&1; g=$?; tail -1 "$OUT/green.txt"
if [ $red -eq 1 ] && [ $g -eq 0 ]; then echo "PASS: подписи разговора — грань PRESS START 1:1"; exit 0; fi
echo "FAIL: красный $red/1, зелёный rc=$g"; exit 1
