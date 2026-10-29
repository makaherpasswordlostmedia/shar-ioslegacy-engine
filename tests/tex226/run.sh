#!/bin/bash
# Гейт правки Роба 226: PNG-текстуры диска в пакете уровня перевёрнуты по вертикали (tests/tex226/check.py). Красный —
# SHR_PNG_FLIP=0 (прежнее: вывески вверх ногами) обязан упасть; зелёный — по умолчанию. Мак, CPU, без эмулятора
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; PY=.venv/bin/python; OUT=build/tex226; mkdir -p "$OUT"
SHR_PNG_FLIP=0 $PY tests/tex226/check.py > "$OUT/red.txt" 2>&1; rr=$?
if [ $rr -ne 0 ] && grep -q "НЕ перевёрнута" "$OUT/red.txt"; then echo "красный (SHR_PNG_FLIP=0): $(tail -1 "$OUT/red.txt")"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН: $(tail -1 "$OUT/red.txt")"; red=0; fi
$PY tests/tex226/check.py > "$OUT/green.txt" 2>&1; rg=$?; echo "зелёный: $(tail -1 "$OUT/green.txt")"
[ $red = 1 ] && [ $rg = 0 ] && echo "PASS" || { echo "FAIL"; exit 1; }
