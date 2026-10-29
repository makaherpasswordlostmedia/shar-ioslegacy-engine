#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
OUT=${OUT_DIR:-build/coins441};mkdir -p "$OUT"
rg -q 'carBoomCoins\(&car' viewer/game.c
for mode in new old;do
 flags="";[ "$mode" != old ] || flags="-DCAR_BOOM_COINS_OLD=1"
 cc -O2 -std=c11 -I viewer $flags tests/coins441/host.c viewer/coins.c viewer/col.c -lm -o "$OUT/$mode"
 if "$OUT/$mode" > "$OUT/$mode.log";then rc=0;else rc=$?;fi
 cat "$OUT/$mode.log"
 if [ "$mode" = new ];then [ "$rc" = 0 ];else [ "$rc" = 1 ];fi
done
echo 'PASS actual boom coin OLD rejected'
