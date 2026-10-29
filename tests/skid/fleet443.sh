#!/bin/bash
# №443: actual car/col/skid for every profile, 2 seconds on each shipped level.
set -e
cd "$(dirname "$0")/../.."
DATA="${1:?usage: fleet443.sh immutable-release-data}"
OUT=build/gates/skid443
mkdir -p "$OUT"
# Ensure the gate's level policy is the policy called by the actual level loader.
rg -q 'skidBeginLevel\(gameLevel\)' viewer/main_levels.h
! rg -q 'skidClear\(gameLevel == 1\)' viewer/main_levels.h
for mode in new old; do
  defs=(); [ "$mode" = new ] || defs=(-DSKID_MARKS_ALL_OLD=1)
  cc -std=c11 -O2 -w -DSKID_HOST -I viewer "${defs[@]}" tests/skid/fleet443.c viewer/skid.c viewer/car.c viewer/col.c -lm -o "$OUT/fleet-$mode"
  for lv in 1 2 3 4 5 6 7; do
    pack="$DATA/l$lv/level.shr"; [ "$lv" != 1 ] || pack="$DATA/level.shr"
    rc=0; "$OUT/fleet-$mode" "$pack" "$lv" > "$OUT/l$lv-$mode.tsv" || rc=$?
    expected=0; [ "$mode" != old ] || [ "$lv" = 1 ] || expected=1
    [ "$rc" = "$expected" ] || { cat "$OUT/l$lv-$mode.tsv"; exit 1; }
    # OLD must retain hover exclusion and fail every wheeled car on L2-L7.
    awk -F '\t' -v mode="$mode" -v lv="$lv" 'NR>1 && NF==7 {n++; expected=(mode=="old" && lv>1 && $3==0)?"FAIL":"PASS"; if($7!=expected)bad++} END {exit (bad || n!=89)}' "$OUT/l$lv-$mode.tsv"
    tail -1 "$OUT/l$lv-$mode.tsv"
  done
done
bash tests/skid/neutral.sh "$DATA/level.shr" > "$OUT/neutral.log"
echo 'PASS: NEW 623/623; OLD 504 wheeled failures; hover 35/35 excluded; neutral regression PASS'
