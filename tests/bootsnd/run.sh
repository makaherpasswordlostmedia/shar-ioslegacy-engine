#!/bin/bash
# Гейт правки Роба 128 (звук включения: щелчок кнопки, раскрутка кулера, бип PC-спикера): tests/bootsnd/host.c на
# viewer/bootbeep.h (Мак, CPU). Сначала КРАСНЫЙ — те же проверки на испорченной партитуре обязаны упасть: без щелчка,
# кулер сразу на полную (нет раскрутки), прежний резкий фильтр писка, кусок не кратен 64; потом ЗЕЛЁНЫЙ. Итог: build/bootsnd/*.txt
# и build/bootsnd_A/B/C.wav (послушать Робу).
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/bootsnd; mkdir -p "$OUT"
red=0
for plant in -DBOOT_SND_CLICK=0 -DBOOT_SND_FAN_TAU=0 -DBOOT_BEEP_LP=0.55f -DBOOT_SND_CHUNK=1000; do
  bash tests/bootsnd/host.sh "$plant" > "$OUT/red_${plant#-D}.txt" 2>&1; rc=$?
  if [ $rc -ne 0 ]; then echo "красный ($plant): упал, как должен — $(grep -m1 -E ': нет|НЕТ' "$OUT/red_${plant#-D}.txt" | cut -c1-100)"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН: $plant прошёл гейт"; fi
done
bash tests/bootsnd/host.sh > "$OUT/green.txt" 2>&1; rc=$?
grep -E "кулер|скорость|RESULT" "$OUT/green.txt"
if [ $red -eq 4 ] && [ $rc -eq 0 ]; then echo "PASS: красный 4/4 пойман, зелёный OK"; exit 0; fi
echo "FAIL: красный $red/4, зелёный rc=$rc"; exit 1
