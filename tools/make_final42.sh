#!/bin/bash
# TEST42 финал: наборы (tools/test42_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t42/READY.txt; date "+%H:%M" > build/t42/BUILDING
if tools/test42_set.sh > build/t42/set.log 2>&1; then
  { echo "SHAR TEST42 · готово $(date '+%Y-%m-%d %H:%M') · integ/test42 $(git rev-parse --short HEAD)"; grep -E "^test42|^SHARVIEW|КАДР ИГРОКА" build/t42/set.log; python3 tools/notoon_check.py build/test42tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t42/READY.txt
  cp build/t42/READY.txt "$HOME/Desktop/SHAR_TEST42/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t42/set.log" > "$HOME/Desktop/SHAR_TEST42/ОШИБКА.txt"; fi
rm -f build/t42/BUILDING
