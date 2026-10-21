#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
DATA=${1:?immutable release};OUT=${OUT_DIR:-build/npcaudio446};mkdir -p "$OUT"
rg -q 'audioWorldSkid\(s,slip(\[i\])?,0\)' viewer/main_collect.h
for mode in new old;do
 flags="";[ "$mode" != old ] || flags="-DNPC_CAR_SKID_OLD=1"
 cc -O2 -std=c11 -DAUDIO_HOST -I viewer $flags tests/npcaudio446/host.c -lm -o "$OUT/$mode"
 for lv in 1 2 3 4 5 6 7;do
  bank="$DATA/l$lv/audio/";[ "$lv" != 1 ] || bank="$DATA/audio/"
  if "$OUT/$mode" "$bank" > "$OUT/l$lv-$mode.log";then rc=0;else rc=$?;fi
  tail -1 "$OUT/l$lv-$mode.log"
  if [ "$mode" = new ];then [ "$rc" = 0 ];else [ "$rc" = 1 ];fi
 done
done
echo 'PASS actual NPC engines/skid, positional voices, cleanup, genuine OLD RED'
