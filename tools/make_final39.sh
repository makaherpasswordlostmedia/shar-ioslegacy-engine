#!/bin/bash
# TEST39 финал: наборы (tools/test39_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t39/READY.txt; date "+%H:%M" > build/t39/BUILDING
if tools/test39_set.sh > build/t39/set.log 2>&1; then
  { echo "SHAR TEST39 · готово $(date '+%Y-%m-%d %H:%M') · integ/test39 $(git rev-parse --short HEAD)"; grep -E "^test39|^SHARVIEW|КАДР ИГРОКА" build/t39/set.log; python3 tools/notoon_check.py build/test39tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t39/READY.txt
  cp build/t39/READY.txt "$HOME/Desktop/SHAR_TEST39/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t39/set.log" > "$HOME/Desktop/SHAR_TEST39/ОШИБКА.txt"; fi
rm -f build/t39/BUILDING
