#!/bin/bash
# Гейт правки Роба 141 (будка и гардероб: одна нижняя строка, без полосы-разделителя, строки pix8, машина 1:1, гардероб по центру).
# Мак, CPU. Сначала КРАСНЫЙ — каждая порча обязана упасть:
#   PHONE_LAYOUT_OLD=1  прежняя раскладка (Accept/Back стопкой, тёмная средняя полоса, звёзды 17 px Ланцошем, гардероб на 189)
#   BOOTH_MIDBAR=1      вернуть тёмную полосу-разделитель
#   BOOTH_PIX8=0        строки дробной гранью пакета (мыло)
#   PIX8W               шаг знака pix8 у раскладки на Маке разошёлся с заголовком движка (порча зеркала на 1 px)
# потом ЗЕЛЁНЫЙ: те же пакеты, что кладёт tools/ship_rules.txt, в build/. Итог: build/booth_layout/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/booth_layout; mkdir -p "$OUT"; PY=.venv/bin/python
exp() {   # $1 — папка; окружение — порча
  mkdir -p "$1"
  $PY tools/shop_export.py --phone-ui --out "$1/phone.shr" > "$1/export.txt" 2>&1 &&
  $PY tools/skins_export.py --ui "$1/wardrobe.shr" --list "$1/skins.txt" >> "$1/export.txt" 2>&1 || { echo "FAIL: экспорт $1"; tail -3 "$1/export.txt"; exit 1; }
}
witness() {   # $1 — 1: испорченное зеркало. Сверка шагов pix8: Мак (ui_export.pix8_adv) против заголовка движка
  cc -std=c11 -O1 -Wall -I viewer tests/ui/booth_pix8w.c -o "$OUT/pix8w" 2> "$OUT/pix8w_build.txt" || { echo "FAIL: сборка свидетеля"; exit 1; }
  "$OUT/pix8w" > "$OUT/pix8w_c.txt"
  PLANT="$1" $PY - "$OUT/pix8w_c.txt" <<'EOF'
import os, sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'hit-and-run-web/tools')
import ui_export as U
bad = 0
for l in open(sys.argv[1]):
    c, a = map(int, l.split()); m = U.pix8_adv(chr(c)) + (1 if os.environ.get('PLANT') == '1' and chr(c) == 'E' else 0)
    if m != a: bad += 1; print(f'FAIL: pix8 шаг {chr(c)!r}: Мак {m}, движок {a}') if bad < 4 else None
print('RESULT', 'FAIL' if bad else 'PASS', 'знаков', sum(1 for _ in open(sys.argv[1]))); sys.exit(1 if bad else 0)
EOF
}
red=0; n=0
for p in PHONE_LAYOUT_OLD=1 BOOTH_MIDBAR=1 BOOTH_PIX8=0; do
  n=$((n + 1)); d="$OUT/red_${p%%=*}"
  env "$p" bash -c "$(declare -f exp); PY=$PY; exp $d" || { echo "КРАСНЫЙ НЕ ПОЙМАН: $p — экспорт упал, а не гейт"; continue; }
  if $PY tests/ui/booth_layout.py "$d/phone.shr" "$d/wardrobe.shr" "$d/skins.txt" > "$d/gate.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: $p прошёл гейт"
  else echo "красный ($p): упал, как должен — $(grep -m1 FAIL: "$d/gate.txt" | cut -c7-110)"; red=$((red + 1)); fi
done
n=$((n + 1))
if witness 1 > "$OUT/red_PIX8W.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: порча зеркала pix8"
else echo "красный (PIX8W): упал, как должен — $(grep -m1 FAIL: "$OUT/red_PIX8W.txt" | cut -c7-90)"; red=$((red + 1)); fi
exp build; cp build/ui/layout_phone.json build/ui/layout_wardrobe.json "$OUT/" 2>/dev/null
witness 0 > "$OUT/green_pix8w.txt" 2>&1; w=$?
$PY tests/ui/booth_layout.py build/phone.shr build/wardrobe.shr build/skins.txt > "$OUT/green.txt" 2>&1; g=$?
cat "$OUT/green.txt"; tail -1 "$OUT/green_pix8w.txt"
if [ $red -eq $n ] && [ $g -eq 0 ] && [ $w -eq 0 ]; then echo "PASS: красный $red/$n пойман, зелёный — пакеты build/phone.shr, build/wardrobe.shr, build/skins.txt"; exit 0; fi
echo "FAIL: красный $red/$n, зелёный rc=$g, свидетель pix8 rc=$w"; exit 1
