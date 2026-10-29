#!/bin/bash
# Правки Роба 37 и 43: плоские детали уровня 1 в эмуляторе (tests/decals/scenario.txt) одним коротким прогоном.
#   tests/decals/emu.sh DIR     DIR = EBOOT.PBP + данные (как у tools/smoke.sh; по умолчанию build/)
# Итог — папка build/smoke/<время>/ (снимки <место>_a/_b.png); лист было/стало: tests/decals/sheet.py ДО ПОСЛЕ.
# Эмулятор — только через tools/smoke.sh -> tools/ppsspp_run.sh (общая очередь, своё окно по PID).
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SMOKE_SCN="$ROOT/tests/decals/scenario.txt" "$ROOT/tools/smoke.sh" "${1:-$ROOT/build}"
