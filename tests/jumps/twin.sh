#!/bin/bash
# Правка Роба 342: трамплины порта против прыжков оригинала (tests/jumps/twin.c, эталон tests/jumps/ramps_ps2.tsv).
#   tests/jumps/twin.sh [level.shr] [--boost] [--trace DIR]
#   tests/jumps/twin.sh --gate [level.shr]   — как есть PASS; прежнее правило 47 (--boost) и без разгона зоны (--no-drive) — FAIL
set -u
cd "$(dirname "$0")/../.."
out=build/tmp/jumps-twin; mkdir -p build/tmp
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/jumps/twin.c viewer/car.c viewer/col.c viewer/props.c \
  viewer/stateprops.c viewer/coins.c -lm -o "$out" || exit 2
if [ "${1:-}" = "--gate" ]; then
  lvl="${2:-build/level.shr}"; bad=0
  "$out" "$lvl" > build/tmp/jumps-twin-ok.txt; r=$?; cat build/tmp/jumps-twin-ok.txt
  [ $r = 0 ] || { echo "гейт: как есть — FAIL"; bad=1; }
  for k in --boost --no-drive; do   # прежнее правило 47 (подброс до верха зоны); без разгона зоны «jump boost»
    "$out" "$lvl" $k > build/tmp/jumps-twin$k.txt; r=$?
    echo "контроль $k: $(tail -1 build/tmp/jumps-twin$k.txt)"
    [ $r != 0 ] || { echo "гейт: контроль $k не покраснел"; bad=1; }
  done
  [ $bad = 0 ] && echo "twin gate: PASS" || echo "twin gate: FAIL"; exit $bad
fi
"$out" "$@"
