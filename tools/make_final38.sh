#!/bin/bash
# TEST38 финал: наборы (tools/test38_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t38/READY.txt; date "+%H:%M" > build/t38/BUILDING
if tools/test38_set.sh > build/t38/set.log 2>&1; then
  { echo "SHAR TEST38 · готово $(date '+%Y-%m-%d %H:%M') · integ/test38 $(git rev-parse --short HEAD)"; grep -E "^test38|^SHARVIEW|КАДР ИГРОКА" build/t38/set.log; python3 tools/notoon_check.py build/test38tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t38/READY.txt
  cp build/t38/READY.txt "$HOME/Desktop/SHAR_TEST38/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t38/set.log" > "$HOME/Desktop/SHAR_TEST38/ОШИБКА.txt"; fi
rm -f build/t38/BUILDING
