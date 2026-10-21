#!/bin/bash
# Правки Роба 247/353 (09.10): перепрыг дома J10 с jumpzone17 против записей PS2 80/90/100 км/ч (tests/jumps/house.c,
# эталон tests/jumps/house_ps2.tsv из tests/jumps/house_ref.py).
#   tests/jumps/house.sh [level.shr] [--trace DIR]
#   tests/jumps/house.sh --gate [level.shr]   — strict: открытые расхождения тоже FAIL
#   tests/jumps/house.sh --known-gate [level.shr] — частичный гейт, не приёмка 247/353
set -u
cd "$(dirname "$0")/../.."
out=build/tmp/jumps-house; mkdir -p build/tmp
SRC="tests/jumps/house.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer"
$CC $SRC -lm -o "$out" || exit 2
if [ "${1:-}" = "--gate" ] || [ "${1:-}" = "--known-gate" ]; then
  strict="--strict"; label="house gate"
  if [ "$1" = "--known-gate" ]; then strict=""; label="house known gate (partial only)"; fi
  .venv/bin/python tests/jumps/house_input.py || exit 2
  lvl="${2:-build/level.shr}"; bad=0
  "$out" "$lvl" $strict > build/tmp/jumps-house-ok.txt; r=$?; cat build/tmp/jumps-house-ok.txt
  [ $r = 0 ] || { echo "гейт: как есть — FAIL"; bad=1; }
  for k in COL_RAMP_RIDGE_OLD COL_RIDGE_EDGE_OLD CAR_AIR_PITCH_OLD; do
    $CC -D$k=1 $SRC -lm -o "$out-old" || exit 2
    "$out-old" "$lvl" $strict > build/tmp/jumps-house-$k.txt; r=$?
    echo "контроль -D$k=1:"; grep -E 'FAIL|PASS|PARTIAL' build/tmp/jumps-house-$k.txt
    [ $r != 0 ] || { echo "гейт: контроль $k не покраснел"; bad=1; }
  done
  [ $bad = 0 ] && echo "$label: PASS" || echo "$label: FAIL"; exit $bad
fi
"$out" "$@"
