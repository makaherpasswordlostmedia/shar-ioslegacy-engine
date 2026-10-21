#!/bin/bash
# Гейт правки 139(1): строка чёрного ящика (viewer/main.c bbSample) с полями трафика «trf N park нарисовано/проснулось ped N»
# влезает в кольцо с худшими значениями (tools/bb_check.py). Мак, только исходник.
# Сначала КРАСНЫЙ — обязан упасть: (1) main.c без полей трафика в формате (как до правки); (2) прежнее кольцо 200 Б с новыми
# полями — хвост строки обрезается. Потом ЗЕЛЁНЫЙ на viewer/main.c. Итог: build/bbtraffic/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/bbtraffic; mkdir -p "$OUT"; PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
red=0
sed 's#trf %d park %d/%d ped %d  ##' viewer/main.c > "$OUT/main_nofields.c"
$PY tools/bb_check.py --src "$OUT/main_nofields.c" > "$OUT/red_old.txt" 2>&1
if [ $? -ne 0 ] && grep -q "нет полей" "$OUT/red_old.txt"; then echo "красный (без полей трафика): упал, как должен"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ПОЙМАН: строка без полей трафика прошла"; fi
$PY tools/bb_check.py --ring 200 > "$OUT/red_ring200.txt" 2>&1
if [ $? -ne 0 ] && grep -q "не влезает" "$OUT/red_ring200.txt"; then echo "красный (кольцо 200 Б): упал, как должен"; red=$((red + 1))
else echo "КРАСНЫЙ НЕ ПОЙМАН: кольцо 200 Б прошло"; fi
$PY tools/bb_check.py > "$OUT/green.txt" 2>&1; rc=$?
grep "FAIL\|RESULT\|кольцо" "$OUT/green.txt"
if [ $red -eq 2 ] && [ $rc -eq 0 ]; then echo "PASS: красный 2/2 пойман, зелёный"; exit 0; fi
echo "FAIL: красный $red/2, зелёный rc=$rc"; exit 1
