#!/bin/bash
# Гейт правки 413б (летающая frink_v не «прозрачная насквозь»; призрачный ship остаётся полупрозрачным).
#   tests/hover/frink_alpha.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/ship_stage); уровень 7 обязателен
# Один прогон безголового эмулятора по tests/hover/frink_alpha.txt; красный контроль («flag carglassold 1») — в том же прогоне
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
DIR="${1:-build/ship_stage}"
SMOKE_HEADLESS=1 SHIP_LEVELS="2 3 4 5 6 7" SMOKE_SCN=tests/hover/frink_alpha.txt SMOKE_MAXT=240 tools/smoke.sh "$DIR" > /dev/null 2>&1
RUN=$(ls -td build/smoke/2* | head -1)
echo "прогон: $RUN"
"$ROOT/.venv/bin/python" tests/hover/frink_alpha.py "$RUN"
