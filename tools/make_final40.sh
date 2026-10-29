#!/bin/bash
# TEST40 финал: наборы (tools/test40_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t40/READY.txt; date "+%H:%M" > build/t40/BUILDING
if tools/test40_set.sh > build/t40/set.log 2>&1; then
  { echo "SHAR TEST40 · готово $(date '+%Y-%m-%d %H:%M') · integ/test40 $(git rev-parse --short HEAD)"; grep -E "^test40|^SHARVIEW|КАДР ИГРОКА" build/t40/set.log; python3 tools/notoon_check.py build/test40tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t40/READY.txt
  cp build/t40/READY.txt "$HOME/Desktop/SHAR_TEST40/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t40/set.log" > "$HOME/Desktop/SHAR_TEST40/ОШИБКА.txt"; fi
rm -f build/t40/BUILDING
