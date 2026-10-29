#!/bin/bash
# Disc rules + real NPC/action/audio/countdown start. No PSP/GPU/physical win claim.
set -eu
cd "$(dirname "$0")/../.."
OUT=${1:-build/streetraces/gate-$(date +%Y%m%d-%H%M%S)}
STAGE=${RACE_STAGE:-build/ship_stage}
mkdir -p "$OUT"
V=viewer
. tools/bots/lib.sh
FLAGS='-std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I viewer -I tools/bots'
cc $FLAGS tests/streetraces/start_host.c $BOTS_LIB -lm -o "$OUT/host" 2>"$OUT/build.log"
cc $FLAGS -DGAME_BONUS_NPC=0 tests/streetraces/start_host.c $BOTS_LIB -lm -o "$OUT/host-old-npc" 2>"$OUT/build-old-npc.log"
cc $FLAGS -DMSN_BREAK_PARTIME=1 tests/streetraces/start_host.c $BOTS_LIB -lm -o "$OUT/host-old-par" 2>"$OUT/build-old-par.log"
.venv/bin/python tests/streetraces/expect.py "$STAGE" "$OUT" >"$OUT/data-green.log"
{ date;git rev-parse HEAD;git status --short;cc --version | head -1; } >"$OUT/identity.txt"
FAIL=0
for lv in 2 3 4 5 6 7;do
 dir="$STAGE/l$lv";args=("$OUT/expect.tsv" "$dir/level.shr" "$STAGE/homer.shr" "$dir/level0$lv.msn")
 if BW_LEVEL="$lv" BW_NO_TRAFFIC=1 BW_AUDIO="$dir/audio/" "$OUT/host" "${args[@]}" >"$OUT/green-l$lv.log" 2>&1;then tail -1 "$OUT/green-l$lv.log";else grep 'FAIL\|RESULT' "$OUT/green-l$lv.log" || true;FAIL=$((FAIL+1));fi
 if BW_LEVEL="$lv" BW_NO_TRAFFIC=1 BW_AUDIO="$dir/audio/" "$OUT/host-old-npc" "${args[@]}" >"$OUT/red-npc-l$lv.log" 2>&1;then echo "FAIL old NPC L$lv passed";FAIL=$((FAIL+1));elif grep -q "^RESULT L$lv FAIL" "$OUT/red-npc-l$lv.log";then tail -1 "$OUT/red-npc-l$lv.log";else echo "FAIL old NPC L$lv crashed";FAIL=$((FAIL+1));fi
 if BW_LEVEL="$lv" BW_NO_TRAFFIC=1 BW_AUDIO="$dir/audio/" "$OUT/host-old-par" "${args[@]}" >"$OUT/red-par-l$lv.log" 2>&1;then echo "FAIL old ParTime L$lv passed";FAIL=$((FAIL+1));elif grep -q 'disc_par_time_failure FAIL' "$OUT/red-par-l$lv.log" && grep -q "^RESULT L$lv FAIL" "$OUT/red-par-l$lv.log";then tail -1 "$OUT/red-par-l$lv.log";else echo "FAIL old ParTime L$lv crashed or failed elsewhere";FAIL=$((FAIL+1));fi
 if .venv/bin/python tests/streetraces/expect.py "$STAGE" "$OUT/plant-l$lv" --plant "$lv" >"$OUT/red-data-l$lv.log" 2>&1;then echo "FAIL data plant L$lv passed";FAIL=$((FAIL+1));elif grep -q '^RESULT data FAIL' "$OUT/red-data-l$lv.log";then tail -1 "$OUT/red-data-l$lv.log";else echo "FAIL data plant L$lv crashed";FAIL=$((FAIL+1));fi
done
printf 'GATE streetraces failures=%s artifacts=%s\n' "$FAIL" "$OUT" | tee "$OUT/summary.txt"
[ "$FAIL" = 0 ]
