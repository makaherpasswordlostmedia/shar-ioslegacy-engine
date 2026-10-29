#!/bin/bash
# Гейт 413б «frink_v прозрачная при разгоне». tests/hover/frink_accel.sh [DIR] (по умолчанию build/ship_stage)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SMOKE_HEADLESS=1 SHIP_LEVELS="2 3 4 5 6 7" SMOKE_SCN=tests/hover/frink_accel.txt SMOKE_MAXT=240 tools/smoke.sh "${1:-build/ship_stage}" > /dev/null 2>&1
RUN=$(ls -td build/smoke/2* | head -1); echo "прогон: $RUN"
"$ROOT/.venv/bin/python" tests/hover/frink_accel.py "$RUN"
