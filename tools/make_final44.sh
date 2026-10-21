#!/bin/bash
# TEST44 финал: наборы (tools/test44_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t44/READY.txt; date "+%H:%M" > build/t44/BUILDING
if tools/test44_set.sh > build/t44/set.log 2>&1; then
  { echo "SHAR TEST44 · готово $(date '+%Y-%m-%d %H:%M') · integ/test44 $(git rev-parse --short HEAD)"; grep -E "^test44|^SHARVIEW|КАДР ИГРОКА" build/t44/set.log; python3 tools/notoon_check.py build/test44tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t44/READY.txt
  cp build/t44/READY.txt "$HOME/Desktop/SHAR_TEST44/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t44/set.log" > "$HOME/Desktop/SHAR_TEST44/ОШИБКА.txt"; fi
rm -f build/t44/BUILDING
