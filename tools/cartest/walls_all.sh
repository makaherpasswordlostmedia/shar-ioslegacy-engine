#!/bin/bash
# One CPU-only command; optional wall-clock minutes per random level sweep.
set -eu
cd "$(dirname "$0")/../.."
ulimit -n 65536
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
exec "$PY" tools/cartest/obstacles_all.py --minutes "${1:-0.25}" "${@:2}"
