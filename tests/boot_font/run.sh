#!/bin/bash
# Гейт правок Роба 152/153 (надписи титульного, загрузки и демо — грань диска 1:1, на пункт крупнее): tests/ui/boot_font_check.py
# по build/boot.shr и build/load.shr, Мак, CPU. Сначала КРАСНЫЙ — прежняя дробная грань boulder_16 x 272/480
# (UI_BOOT_SOFT=1 tools/load_export.py) обязана упасть, потом ЗЕЛЁНЫЙ — boulder_16@1. Зелёные пакеты пишутся последними:
# build/boot.shr, build/load.shr и build/ui/layout_*.json — новые. Итог: build/boot_font/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; OUT=build/boot_font; mkdir -p "$OUT"
BOOT=bootload,splash,demo; LOAD=loading,loadingfe
UI_BOOT_SOFT=1 "$PY" tools/load_export.py > "$OUT/red_pack.txt" 2>&1 || { echo "FAIL: красные пакеты не собрались"; exit 1; }
red=0
for p in "boot $BOOT" "load $LOAD"; do set -- $p
  "$PY" tests/ui/boot_font_check.py --pack $1 --screens $2 > "$OUT/red_$1.txt" 2>&1; rc=$?
  if [ $rc -ne 0 ] && grep -q "масштаб не целый" "$OUT/red_$1.txt"; then echo "красный $1.shr (UI_BOOT_SOFT=1, boulder_16 x 0.567): упал, как должен"; red=$((red + 1))
  else echo "КРАСНЫЙ $1.shr НЕ ПОЙМАН (rc=$rc)"; fi
done
"$PY" tools/load_export.py > "$OUT/green_pack.txt" 2>&1 || { echo "FAIL: пакеты не собрались"; exit 1; }
green=0
for p in "boot $BOOT" "load $LOAD"; do set -- $p
  "$PY" tests/ui/boot_font_check.py --pack $1 --screens $2 > "$OUT/green_$1.txt" 2>&1 && green=$((green + 1)); tail -1 "$OUT/green_$1.txt"
done
if [ $red -eq 2 ] && [ $green -eq 2 ]; then echo "PASS: красный 2/2 пойман, зелёный 2/2 — надписи 1:1 с диска"; exit 0; fi
echo "FAIL: красный $red/2, зелёный $green/2"; exit 1
