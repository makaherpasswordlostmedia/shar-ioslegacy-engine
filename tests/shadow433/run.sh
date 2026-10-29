#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
OUT=${OUT_DIR:-build/shadow433};mkdir -p "$OUT"
cc -std=c11 -O2 -DcolGround=colGroundActual -I viewer -c viewer/col.c -o "$OUT/col.o"
for mode in new old;do
 flags="-DSHADOW_OLD=1";[ "$mode" != old ] || flags="-DSHADOW_OLD=1 -DCAR_SHADOW_V2_OLD=1"   # №522: гейт №433 проверяет прежнюю плоскость, поэтому только при SHADOW_OLD=1
 cc -std=c11 -O2 -ffunction-sections -DSKIN_HOST -I tests/shadow433/stub -I viewer $flags tests/shadow433/host.c viewer/carvis.c viewer/car.c "$OUT/col.o" -lm -o "$OUT/$mode"
 if "$OUT/$mode" > "$OUT/$mode.log";then rc=0;else rc=$?;fi
 cat "$OUT/$mode.log"
 if [ "$mode" = new ];then [ "$rc" = 0 ];else [ "$rc" = 1 ];fi
done
echo 'PASS actual CAR_SHADOW_V2_OLD rejected'
