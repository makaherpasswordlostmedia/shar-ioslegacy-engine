#!/bin/bash
# Independent disc locations -> live game APIs on each level.
# Default exports only collect packs, no game assets enter Git or PSP.
# --reuse uses packs in build/collect/alllevels from the prior run.
set -eu
cd "$(dirname "$0")/../.."
REUSE=0
if [ "${1:-}" = --reuse ]; then REUSE=1; shift; fi
STAGE=${COLLECT_STAGE:-build/ship_stage}
PACKS=build/collect/alllevels
OUT=${1:-build/collect/gate-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$OUT" "$PACKS"
PY=.venv/bin/python
V=viewer
. tools/bots/lib.sh
cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I viewer -I tools/bots tests/collect/alllevels.c $BOTS_LIB -lm -o "$OUT/host" 2>"$OUT/build.log"
cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -DCOLLECT_SPAWN_OLD -I viewer -I tools/bots tests/collect/alllevels.c $BOTS_LIB -lm -o "$OUT/host-old" 2>"$OUT/build-old.log"
{ date; git rev-parse HEAD; git status --short; cc --version | head -1; } >"$OUT/identity.txt"
if [ "$REUSE" = 0 ]; then
 for n in 2 3 4 5 6 7; do
  "$PY" tools/collect_export.py --level "$n" --out "$PACKS/collect-l$n.shr" >"$OUT/export-l$n.log" 2>&1
  COLLECT_INTERIOR_OLD=1 "$PY" tools/collect_export.py --level "$n" --out "$PACKS/collect-l$n-old.shr" >"$OUT/export-l$n-old.log" 2>&1
 done
 for n in 2 3 5 6; do
  "$PY" tools/interior_export.py --level "$n" --no-gfx --outdir "$PACKS" >"$OUT/interior-l$n.log" 2>&1
  ROOM_INTERIOR_OLD=1 "$PY" tools/interior_export.py --level "$n" --no-gfx --outdir "$PACKS/old-interiors/l$n" >"$OUT/interior-l$n-old.log" 2>&1
  cp -c "$PACKS/old-interiors/l$n/interiors-l$n.bin" "$PACKS/interiors-l$n-old.bin"
 done
 bash tests/collect/stage.sh "$STAGE"
fi
FAIL=0
run() {
 BW_LEVEL="$n" BW_NO_TRAFFIC=1 BW_NO_AUDIO=1 BW_COLLECT="$pack" "$@" "$OUT/expect-l$n.tsv" "$pack" "$lev" "$STAGE/homer.shr" "${plant:-}" >"$log" 2>&1
}
for n in 1 2 3 4 5 6 7; do
 "$PY" tests/collect/expect.py "$n" >"$OUT/expect-l$n.tsv"
 pack="$STAGE/l$n/collect-l$n.shr"; lev="$STAGE/l$n/level.shr"
 if [ "$n" = 1 ]; then pack="$STAGE/collect-l1.shr"; lev="$STAGE/level.shr"; fi
 plant=""; log="$OUT/green-l$n.log"
 if run "$OUT/host"; then tail -1 "$log"; else grep 'FAIL\|RESULT' "$log"; FAIL=$((FAIL+1)); fi
 for plant in card wasp gag coin wrench rooms roomgfx; do
  log="$OUT/red-l$n-$plant.log"
  if run "$OUT/host"; then echo "FAIL L$n red $plant passed"; FAIL=$((FAIL+1)); else
   if ! grep -q "^RESULT L$n FAIL" "$log"; then echo "FAIL L$n red $plant crashed instead of observing a failure"; FAIL=$((FAIL+1)); else echo "RED L$n $plant observed"; fi
  fi
 done
 plant=""
 if [ "$n" = 2 ] || [ "$n" = 5 ]; then
  log="$OUT/old-spawn-l$n.log"
  if run "$OUT/host-old"; then echo "FAIL L$n old spawn passed"; FAIL=$((FAIL+1)); else
   grep 'wasp.total\|RESULT' "$log"; grep -q "^CHECK L$n wasp.spawn.*FAIL" "$log" || FAIL=$((FAIL+1))
  fi
 fi
 if [ "$n" = 2 ] || [ "$n" = 3 ] || [ "$n" = 5 ] || [ "$n" = 6 ]; then
  log="$OUT/old-roomdoor-l$n.log"
  export COLLECT_ROOM_PACK="$PACKS/interiors-l$n-old.bin"
  if run "$OUT/host"; then echo "FAIL L$n old room door passed"; FAIL=$((FAIL+1)); else
   grep 'room.door.*FAIL\|RESULT' "$log"; grep -q "^CHECK L$n room.door.*FAIL" "$log" || FAIL=$((FAIL+1))
  fi
  unset COLLECT_ROOM_PACK
 fi
 if [ "$n" = 2 ] || [ "$n" = 3 ] || [ "$n" = 7 ]; then
  pack="$PACKS/collect-l$n-old.shr"; log="$OUT/old-interior-l$n.log"
  if run "$OUT/host"; then echo "FAIL L$n old interior passed"; FAIL=$((FAIL+1)); else
   grep 'gag.room.*FAIL\|RESULT' "$log"; grep -q "^CHECK L$n gag.room.*FAIL" "$log" || FAIL=$((FAIL+1))
  fi
 fi
 done
printf 'GATE collect L1-L7 failures=%s artifacts=%s\n' "$FAIL" "$OUT" | tee "$OUT/summary.txt"
[ "$FAIL" = 0 ]
