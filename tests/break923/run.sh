#!/bin/bash
# №923 гейт: осколки обломка летят по скорости машины (угол ≤ 20°), все типы обломков уровня 1..7; красный — spBreak (как было)
#   tests/break923/run.sh        новое: PASS; tests/break923/run.sh old   — прежнее: должно упасть
cd "$(dirname "$0")/../.."; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test58tour/PSP/GAME/SHARTEST15}; O=build/tests/break923; mkdir -p $O
cc -std=c11 -O1 -DSKIN_HOST -I viewer tests/break923/host.c viewer/props.c viewer/stateprops.c viewer/col.c viewer/car.c viewer/coins.c -lm -o $O/h 2>&1 | grep -E 'error' && exit 2
rc=0
for L in 1 2 3 4 5 6 7; do f=$SET/level.shr; [ $L -gt 1 ] && f=$SET/l$L/level.shr; echo "L$L:"; $O/h $f $1 || rc=1; done
[ $rc = 0 ] && echo "PASS break923" || echo "FAIL break923"; exit $rc
