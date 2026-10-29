#!/bin/bash
# TEST45 финал: наборы (tools/test45_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t45/READY.txt; date "+%H:%M" > build/t45/BUILDING
if tools/test45_set.sh > build/t45/set.log 2>&1; then
  { echo "SHAR TEST45 · готово $(date '+%Y-%m-%d %H:%M') · integ/test45 $(git rev-parse --short HEAD)"; grep -E "^test45|^SHARVIEW|КАДР ИГРОКА" build/t45/set.log; python3 tools/notoon_check.py build/test45tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t45/READY.txt
  cp build/t45/READY.txt "$HOME/Desktop/SHAR_TEST45/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t45/set.log" > "$HOME/Desktop/SHAR_TEST45/ОШИБКА.txt"; fi
rm -f build/t45/BUILDING
