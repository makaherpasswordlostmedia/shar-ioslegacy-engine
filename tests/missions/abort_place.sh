#!/bin/bash
# №369: полный адаптер игры, все миссии L1–L7, пешком и за рулём
set -eu
cd "$(dirname "$0")/../.."
O=build/codex-terminal/rob-pack/369; mkdir -p "$O"
V=viewer; . tools/bots/lib.sh
cc -std=c11 -O2 -DSKIN_HOST -I viewer -I tools/bots tests/missions/abort_place.c $BOTS_LIB -lm -o "$O/abort_place"
git show e4ae044:viewer/game_msn.c > "$O/game_msn_old.c"
OLD_LIB="${BOTS_LIB/viewer\/game_msn.c/$O\/game_msn_old.c}"
cc -std=c11 -O2 -DSKIN_HOST -I viewer -I tools/bots tests/missions/abort_place.c $OLD_LIB -lm -o "$O/abort_old"
if "$O/abort_old" build/level.shr build/homer.shr build/missions/level01.msn > "$O/l1-red.log" 2>&1; then
  echo 'FAIL: старый код сохранил положение'; exit 1
fi
tail -1 "$O/l1-red.log"
for N in 1 2 3 4 5 6 7; do
  LEVEL=build/level.shr; [ "$N" = 1 ] || LEVEL="build/levels/l$N/level.shr"
  printf -v MSN 'build/missions/level%02d.msn' "$N"
  "$O/abort_place" "$LEVEL" build/homer.shr "$MSN" > "$O/l$N-green.log" 2>&1
  tail -1 "$O/l$N-green.log"
done
echo 'PASS: старый код красный, 180 отмен на L1–L7 зелёные, Retry переносит'
