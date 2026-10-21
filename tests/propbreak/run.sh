#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
OUT=${OUT_DIR:-build/propbreak};mkdir -p "$OUT"
for mode in new old;do
 flags="";[ "$mode" != old ] || flags="-DPROP_BREAK_PASS_OLD=1"
 cc -std=c11 -O2 -I viewer $flags tests/propbreak/host.c viewer/stateprops.c viewer/props.c viewer/coins.c viewer/car.c viewer/col.c -lm -o "$OUT/$mode"
 if "$OUT/$mode" "$@" > "$OUT/$mode.log";then rc=0;else rc=$?;fi
 cat "$OUT/$mode.log"
 if [ "$mode" = new ];then [ "$rc" = 0 ];else [ "$rc" = 1 ];fi
done
echo 'PASS real PROP_BREAK_PASS_OLD rejected'
