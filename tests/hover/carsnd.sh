#!/bin/bash
# Гейт правки 413а (звук парящих машин: свой мотор и свой занос из данных, без шин). Нужен пакет звука L7 после правки
# (tools/sound_export.py --level 7: профили ship, witchcar, hbike_v, frink_v со своим заносом).
#   tests/hover/carsnd.sh [DIR]   DIR — EBOOT + данные (по умолчанию build/ship_stage)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
DIR="${1:-build/ship_stage}"
SMOKE_HEADLESS=1 SHIP_LEVELS="2 3 4 5 6 7" SMOKE_SCN=tests/hover/carsnd.txt SMOKE_MAXT=280 tools/smoke.sh "$DIR" > /dev/null 2>&1
RUN=$(ls -td build/smoke/2* | head -1)
echo "прогон: $RUN"
SAB="$DIR/l7/audio/sfx.sab"; [ -f "$SAB" ] || SAB=build/levels/l7/audio/sfx.sab
"$ROOT/.venv/bin/python" tests/hover/carsnd.py "$RUN" "$SAB"
