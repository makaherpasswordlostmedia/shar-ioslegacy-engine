#!/bin/bash
# №902 замер: от подхода машины вплотную (35 см) к хрупкому предмету до события удара, все 7 уровней, новое против SP_WALL902_OLD=1
cd "$(dirname "$0")/../.."; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test52tour/PSP/GAME/SHARTEST15}; O=build/tests/smash902; mkdir -p $O
for v in 0 1; do cc -std=c11 -O2 -DSKIN_HOST -DSP_WALL902_OLD=$v -I viewer tests/smash902/host.c viewer/props.c viewer/col.c viewer/car.c viewer/coins.c -lm -o $O/h$v || exit 2; done
for L in 1 2 3 4 5 6 7; do f=$SET/level.shr; [ $L -gt 1 ] && f=$SET/l$L/level.shr; echo "L$L новое: $($O/h0 $f)"; echo "   прежнее: $($O/h1 $f)"; done
