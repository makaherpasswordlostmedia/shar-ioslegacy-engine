#!/bin/bash
# Набор уровня 1 для смоука этой копии: build/lm_stage = EBOOT этой копии (viewer/build/EBOOT.PBP) + данные уровня 1,
# персонажи и ролики из готового набора основной копии (build/ship_stage, только чтение, клон файлов). Данные уровня 1
# механики уровней 2–7 не меняют (SPR1 уровня 1 и collect-l1 побайтно прежние — tests/levelmech/spr1_same.py, cmp).
#   tests/levelmech/stage.sh && tools/smoke.sh build/lm_stage
set -e; cd "$(dirname "$0")/../.."
MAIN=${SHAR_MAIN:-$HOME/Downloads/shar-psp}; S=build/lm_stage
rm -rf "$S"; mkdir -p "$S"
cp viewer/build/EBOOT.PBP "$S/"
while IFS='|' read -r f src; do
  from="$MAIN/build/ship_stage/$f"; [ -f "$from" ] || from="$MAIN/$src"
  [ -f "$from" ] || { echo "нет $f" >&2; continue; }
  mkdir -p "$S/$(dirname "$f")"; cp -c "$from" "$S/$f" 2>/dev/null || cp "$from" "$S/$f"
done < <(SHIP_LEVELS="" tools/ship_files.sh --pairs)
echo "$S: $(find "$S" -type f | wc -l | tr -d ' ') файлов"
