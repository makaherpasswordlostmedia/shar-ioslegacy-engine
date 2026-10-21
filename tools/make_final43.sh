#!/bin/bash
# TEST43 финал: наборы (tools/test43_set.sh, проверки кадра в эмуляторе) -> метка READY.txt; пока идёт сборка — метка BUILDING (кнопка на рабочем столе ждёт)
cd "$(dirname "$0")/.."
rm -f build/t43/READY.txt; date "+%H:%M" > build/t43/BUILDING
if tools/test43_set.sh > build/t43/set.log 2>&1; then
  { echo "SHAR TEST43 · готово $(date '+%Y-%m-%d %H:%M') · integ/test43 $(git rev-parse --short HEAD)"; grep -E "^test43|^SHARVIEW|КАДР ИГРОКА" build/t43/set.log; python3 tools/notoon_check.py build/test43tour/PSP/GAME/SHARTEST15 2>&1 | tail -7; } > build/t43/READY.txt
  cp build/t43/READY.txt "$HOME/Desktop/SHAR_TEST43/ГОТОВО.txt"
else echo "СБОРКА НЕ УДАЛАСЬ $(date '+%H:%M'): build/t43/set.log" > "$HOME/Desktop/SHAR_TEST43/ОШИБКА.txt"; fi
rm -f build/t43/BUILDING
