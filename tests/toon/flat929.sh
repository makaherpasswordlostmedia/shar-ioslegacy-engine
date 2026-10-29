#!/bin/bash
# Гейт №929 (хост, без эмулятора): tests/toon/flat929.sh НАБОР. FLAT929_RED=1 — красный контроль (прежние правила ASPH929_OLD / WALL929_OLD): гейт обязан упасть
cd "$(dirname "$0")/../.."
PK=${1:?НАБОР}
if [ "${FLAT929_RED:-}" = 1 ]; then
  ASPH929_OLD=1 WALL929_OLD=1 python3 tests/toon/flat929.py "$PK" | tail -4; rc=${PIPESTATUS[0]}
  [ $rc -ne 0 ] && echo "красный упал, как должен" || { echo "FAIL красный не упал"; exit 1; }; exit 0
fi
python3 tests/toon/flat929.py "$PK"
