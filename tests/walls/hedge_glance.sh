#!/bin/bash
set -u
cd "$(dirname "$0")/../.."
PY=${PY:-.venv/bin/python}; [ -x "$PY" ] || PY=python3
"$PY" tests/walls/hedge_glance.py; g=$?
"$PY" tests/walls/hedge_glance.py --old; r=$?
if [ "$g" = 0 ] && [ "$r" = 1 ]; then
  echo 'PASS: hedge glances green, old friction red'; exit 0
fi
echo "FAIL: green=$g old=$r"; exit 1
