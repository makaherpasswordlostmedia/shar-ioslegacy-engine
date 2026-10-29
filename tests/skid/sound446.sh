#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
DATA=${1:?immutable release directory};OUT=${OUT_DIR:-build/skid-sound446};mkdir -p "$OUT"
grep -q 'sndSkid(skidSoundLevel(&car, &in)' viewer/main_loop.h
for mode in new old;do
 flags="";[ "$mode" != old ] || flags="-DPLAYER_SKID_SOUND_OLD=1"
 cc -O2 -std=c11 -DAUDIO_HOST -DSKID_HOST -I viewer $flags tests/skid/sound446.c viewer/skid.c viewer/car.c viewer/col.c -lm -o "$OUT/$mode"
 for lv in 1 2 3 4 5 6 7;do
  bank="$DATA/l$lv/audio/";[ "$lv" != 1 ] || bank="$DATA/audio/"
  if "$OUT/$mode" "$bank" > "$OUT/l$lv-$mode.log";then rc=0;else rc=$?;fi
  tail -1 "$OUT/l$lv-$mode.log"
  if [ "$mode" = new ];then [ "$rc" = 0 ];else [ "$rc" = 1 ];fi
 done
done
echo 'PASS actual braking skid PCM; authored blank remains silent; genuine OLD red on all7'
