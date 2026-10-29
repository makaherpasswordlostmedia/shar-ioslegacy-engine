#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out=build/wreck355-c3; mkdir -p "$out"
V=viewer; source tools/bots/lib.sh
cc -std=c11 -O2 -w -DSKIN_HOST -Iviewer -Itools/bots tests/husk/repair355.c $BOTS_LIB -lm -o "$out/repair355" > "$out/compile.log" 2>&1
for L in 1 2 3 4 5 6 7; do
  pkg="build/ship_stage/l$L"; if [ "$L" = 1 ]; then pkg=build/ship_stage; fi
  BW_LEVEL="$L" "$out/repair355" "$pkg/level.shr" build/ship_stage/homer.shr "$pkg/level0$L.msn" 0 > "$out/l$L-new.log"
  for red in 1 2; do
    if BW_LEVEL="$L" "$out/repair355" "$pkg/level.shr" build/ship_stage/homer.shr "$pkg/level0$L.msn" "$red" > "$out/l$L-red$red.log"; then echo "blind red$red L$L";exit 1;fi
    expected=repaired-state; if [ "$red" = 2 ]; then expected=NPC-solid-after-repair; fi
    rg -q "CHECK $expected FAIL" "$out/l$L-red$red.log" || { echo "unrelated red$red L$L";exit 1; }
  done
  echo "L$L GREEN + RED broken-repair/noSolid"
done
bash tests/husk/run.sh > "$out/husk-existing-old.log" 2>&1
echo "PASS repaired7, negative14, existing CAR_HUSK_OLD"
