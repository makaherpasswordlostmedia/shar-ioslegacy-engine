#!/bin/bash
# Гейт правки 126 (пузырь сообщений: пиксельный шрифт msx 8×8, текст от поля пузыря, жёсткий перенос): tests/ui/pix8.c на
# логике viewer/ui_layout.h + build/ui.shr (Мак, CPU). Сначала КРАСНЫЙ — каждая порча обязана упасть: прежнее начало текста
# (UI_OBJ_OLD), прежний перенос (UI_WRAP_OLD), промежуточная альфа (PLANT_ALPHA), сдвиг таблицы глифов (PLANT_MSX);
# потом ЗЕЛЁНЫЙ. Итог: build/pix8/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/pix8; mkdir -p "$OUT"
build() { cc -std=c11 -O1 -Wall -Wno-unused-function "$2" -I viewer tests/ui/pix8.c -o "$OUT/pix8_$1" 2> "$OUT/build_$1.txt" ||
          { echo "FAIL: сборка ($1)"; head -5 "$OUT/build_$1.txt"; exit 1; }; }
red=0; plants="UI_OBJ_OLD UI_WRAP_OLD PLANT_ALPHA PLANT_MSX PIX8_BOLD=0 UI_OBJ_PAD=0"   # PIX8_BOLD=0 — тонкий 8×8 (Роб: «худой») обязан упасть
for p in $plants; do
  build "$p" "-D$p"; "$OUT/pix8_$p" build/ui.shr > "$OUT/red_$p.txt" 2>&1; rc=$?
  case "$p" in UI_OBJ_OLD|UI_OBJ_PAD=0) want="FAIL L1" ;; UI_WRAP_OLD) want="FAIL L3" ;; PLANT_ALPHA) want="FAIL F1" ;; *) want="FAIL F2" ;; esac
  if [ $rc = 1 ] && grep -q "^$want" "$OUT/red_$p.txt"; then echo "красный ($p): упал, как должен — $(grep -m1 FAIL "$OUT/red_$p.txt" | cut -c6-90)"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН: $p прошёл гейт"; fi
done
build green -DGREEN; "$OUT/pix8_green" build/ui.shr > "$OUT/green.txt" 2>&1; rc=$?
cat "$OUT/green.txt"
if [ $red -eq 6 ] && [ $rc -eq 0 ]; then echo "PASS: красный 6/6 пойман, зелёный $(grep -m1 RESULT "$OUT/green.txt" | cut -d' ' -f2)"; exit 0; fi
echo "FAIL: красный $red/6, зелёный rc=$rc"; exit 1
