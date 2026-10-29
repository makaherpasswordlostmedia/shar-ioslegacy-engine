#!/bin/bash
# Rob350: full DEV bonus progress while NPC action replays remain accessible.
# Only host logic; no PSP/GPU acceptance is implied.
set -eu
cd "$(dirname "$0")/../../.."
OUT=${1:-build/devbonus/gate-$(date +%Y%m%d-%H%M%S)}
STAGE=${DEV_STAGE:-build/ship_stage}
REF=${DEV_REFERENCE:-$(cd "$(git rev-parse --git-common-dir)/.." && pwd)}
mkdir -p "$OUT"
V=viewer
. tools/bots/lib.sh
FLAGS='-std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I viewer -I tools/bots'
cc $FLAGS tests/savegame/devsave/bonus_host.c $BOTS_LIB viewer/savegame.c -lm -o "$OUT/host" 2>"$OUT/build.log"
cc $FLAGS -DGAME_MSN_DEV_BONUS_OLD tests/savegame/devsave/bonus_host.c $BOTS_LIB viewer/savegame.c -lm -o "$OUT/host-old-bonus" 2>"$OUT/build-old-bonus.log"
cc $FLAGS -DSV_DEV_GAGS_OLD tests/savegame/devsave/bonus_host.c $BOTS_LIB viewer/savegame.c -lm -o "$OUT/host-old-gags" 2>"$OUT/build-old-gags.log"
.venv/bin/python tests/savegame/devsave/bonus_expect.py >"$OUT/expect.tsv" 2>"$OUT/engine-coded.txt"
{ date;git rev-parse HEAD;git status --short;cc --version | head -1; } >"$OUT/identity.txt"
FAIL=0
for n in 1 2 3 4 5 6 7; do
 dir="$STAGE/l$n";msn="$dir/level0$n.msn";collect="${DEV_COLLECT_PACKS:-build/devbonus}/collect-l$n.shr"
 if [ "$n" = 1 ]; then dir="$STAGE";msn="$dir/level01.msn";fi
 if [ ! -f "$collect" ]; then
  if [ "$n" = 1 ]; then collect="$STAGE/collect-l1.shr";else collect="$REF/build/levels/l$n/collect-l$n.shr";fi
 fi
 args=("$OUT/expect.tsv" "$dir/level.shr" "$STAGE/homer.shr" "$msn" "$collect")
 if BW_LEVEL="$n" BW_NO_TRAFFIC=1 BW_NO_AUDIO=1 "$OUT/host" "${args[@]}" >"$OUT/green-l$n.log" 2>&1;then tail -1 "$OUT/green-l$n.log";else grep 'FAIL\|RESULT' "$OUT/green-l$n.log" || true;FAIL=$((FAIL+1));fi
 for p in bonus gags;do
  log="$OUT/red-$p-l$n.log"
  if BW_LEVEL="$n" BW_NO_TRAFFIC=1 BW_NO_AUDIO=1 "$OUT/host-old-$p" "${args[@]}" >"$log" 2>&1;then echo "FAIL old $p L$n passed";FAIL=$((FAIL+1));else
   if grep -q "^RESULT L$n FAIL" "$log";then grep "dev.full_bonus.*FAIL\|dev.gag_count.*FAIL\|RESULT" "$log";else echo "FAIL old $p L$n did not produce an observed assertion failure";FAIL=$((FAIL+1));fi
  fi
 done
done
printf 'GATE devbonus L1-L7 failures=%s artifacts=%s\n' "$FAIL" "$OUT" | tee "$OUT/summary.txt"
[ "$FAIL" = 0 ]
