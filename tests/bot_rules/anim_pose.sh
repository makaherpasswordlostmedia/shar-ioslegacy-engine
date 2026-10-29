#!/bin/bash
set -eu
ulimit -n 65536
out=${1:-build/bot-rules/anim-pose}
data=${2:-../shar-psp/build/qa-final-75226ea}
mkdir -p "$out"
for old in 0 1; do
 cc -std=c11 -O2 -DSKIN_HOST -DANIM_COL_POSE_OLD=$old -Iviewer tests/bot_rules/anim_pose.c viewer/animobj.c viewer/stateprops.c viewer/col.c viewer/props.c viewer/coins.c viewer/car.c -lm -o "$out/probe-$old"
 fail=0
 for l in 1 2 3 4 5 6 7; do
  lv="$data/l$l/level.shr"; [ "$l" = 1 ] && lv="$data/level.shr"
  "$out/probe-$old" "$lv" > "$out/l$l-old$old.txt" || fail=$((fail+1))
  tail -1 "$out/l$l-old$old.txt"
 done
 if [ "$old" = 0 ]; then [ "$fail" = 0 ]; else [ "$fail" -gt 0 ]; fi
 echo "ANIM_COL_POSE_OLD=$old failing_levels=$fail expected"
done
