#!/bin/bash
# TEST36 финал: наборы (tools/test36_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t36/READY.txt; date "+%H:%M" > build/t36/BUILDING
if tools/test36_set.sh > build/t36/set.log 2>&1; then
  { echo "SHAR TEST36 · готово $(date '+%Y-%m-%d %H:%M') · integ/test36 $(git rev-parse --short HEAD)"; grep -E "^test36|^SHARVIEW|КАДР ИГРОКА" build/t36/set.log; python3 tools/notoon_check.py build/test36tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t36/READY.txt
  cp build/t36/READY.txt "$HOME/Desktop/SHAR_TEST36/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t36/set.log" > "$HOME/Desktop/SHAR_TEST36/ОШИБКА.txt"; fi
rm -f build/t36/BUILDING
