#!/bin/bash
set -eu
ulimit -n 65536
out=${1:-build/bot-rules/curb}
mkdir -p "$out"
for old in 0 1; do
 cc -std=c11 -O2 -DCAR_CURB_STEP_OLD=$old -Iviewer tests/bot_rules/curb.c viewer/car.c viewer/col.c -lm -o "$out/probe-$old"
 if "$out/probe-$old" > "$out/old$old.txt"; then rc=0; else rc=$?; fi
 tail -1 "$out/old$old.txt"
 if [ "$old" = 0 ]; then [ "$rc" = 0 ]; else [ "$rc" = 1 ]; fi
done
