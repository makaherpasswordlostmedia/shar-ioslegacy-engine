#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
DATA="${1:?usage: prefetch444.sh immutable-data}"
OUT=build/gates/npc444; mkdir -p "$OUT/obj"
V=viewer; . tools/bots/lib.sh
for src in $BOTS_LIB; do
  obj="$OUT/obj/$(basename "$src" .c).o"
  cc -std=c11 -O2 -w -DSKIN_HOST -ffunction-sections -fdata-sections -I viewer -I tools/bots -c "$src" -o "$obj"
done
for mode in new old; do
  defs=''; [ "$mode" = new ] || defs='-DNPC_PREFETCH_OLD=1'
  cc -std=c11 -O2 -w $defs -DsceIoLseek=sceIoLseek32 -ffunction-sections -fdata-sections -I tests/crash_school/stub -I pspdev/psp/sdk/include -I viewer -I tools/bots -c tests/npc/prefetch444_host.c -o "$OUT/host-$mode.o"
  cc "$OUT/host-$mode.o" "$OUT"/obj/*.o -Wl,-dead_strip -lm -o "$OUT/prefetch-$mode"
  for lv in 1 2 3 4 5 6 7; do
    prefix="$DATA/l$lv"; [ "$lv" != 1 ] || prefix="$DATA"
    rc=0; BW_NO_TRAFFIC=1 "$OUT/prefetch-$mode" "$prefix/level.shr" "$DATA/homer.shr" "$prefix/level0$lv.msn" "$DATA" > "$OUT/l$lv-$mode.log" || rc=$?
    tail -2 "$OUT/l$lv-$mode.log"
    if [ "$mode" = new ]; then [ "$rc" = 0 ]; else [ "$rc" = 1 ] && rg -q 'eye_boundary=88m FAIL' "$OUT/l$lv-$mode.log"; fi
  done
done
echo 'PASS NEW7/7 actual model loads; OLD7/7 late race NPCs'
