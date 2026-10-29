#!/bin/bash
# Each old layer must genuinely fail: runtime classification, missing baked glyph.
set -euo pipefail
cd "$(dirname "$0")/../.."
SOURCE="${1:-../shar-psp/build}"
mkdir -p build/race-unknown
V=viewer
. tools/bots/lib.sh
cc -std=c11 -O2 -DSKIN_HOST -I viewer -I tools/bots tests/ui/race_unknown_host.c $BOTS_LIB -lm -o build/race-unknown/host
cc -std=c11 -O2 -DSKIN_HOST -DC3_RACE_OFFROAD_OLD -I viewer -I tools/bots tests/ui/race_unknown_host.c $BOTS_LIB -lm -o build/race-unknown/old
LEVEL=1 .venv/bin/python tools/ui_export.py pack --out build/race-unknown/ui.shr > build/race-unknown/export.log 2>&1
C3_RACE_OFFROAD_OLD=1 LEVEL=1 .venv/bin/python tools/ui_export.py pack --out build/race-unknown/ui-old.shr > build/race-unknown/export-old.log 2>&1
python3 tests/ui/race_unknown_gate.py --source "$SOURCE"
