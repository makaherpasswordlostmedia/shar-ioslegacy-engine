#!/bin/bash
# TEST37 финал: наборы (tools/test37_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t37/READY.txt; date "+%H:%M" > build/t37/BUILDING
if tools/test37_set.sh > build/t37/set.log 2>&1; then
  { echo "SHAR TEST37 · готово $(date '+%Y-%m-%d %H:%M') · integ/test37 $(git rev-parse --short HEAD)"; grep -E "^test37|^SHARVIEW|КАДР ИГРОКА" build/t37/set.log; python3 tools/notoon_check.py build/test37tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t37/READY.txt
  cp build/t37/READY.txt "$HOME/Desktop/SHAR_TEST37/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t37/set.log" > "$HOME/Desktop/SHAR_TEST37/ОШИБКА.txt"; fi
rm -f build/t37/BUILDING
