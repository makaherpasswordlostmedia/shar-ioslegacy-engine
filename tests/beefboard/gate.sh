#!/bin/bash
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-.venv/bin/python}
PACKS=${1:?corrected level packs root}; OLD=${2:?original packs root}
"$PY" tests/beefboard/check.py --packs "$PACKS" --old-packs "$OLD"; g=$?
SHR_ANIMCOL_FRAME_OLD=1 "$PY" tests/beefboard/check.py --packs "$PACKS" --old-packs "$OLD"; r=$?
if [ "$g" = 0 ] && [ "$r" = 1 ]; then echo 'PASS: green source+packs, old export red'; exit 0; fi
echo "FAIL: green=$g old=$r"; exit 1
