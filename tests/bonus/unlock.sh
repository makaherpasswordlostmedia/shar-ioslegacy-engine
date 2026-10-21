#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
out=${OUT_DIR:-build/bonus-unlock-host}
stage=${1:-build/bonus-unlock-stage}
mkdir -p "$out"
V=viewer
. tools/bots/lib.sh
cc -std=c11 -O2 -DSKIN_HOST -I viewer -I tools/bots tests/bonus/unlock_host.c $BOTS_LIB viewer/savegame.c -lm -o "$out/green"
cc -std=c11 -O2 -DSKIN_HOST -DBONUS_UNLOCK_OLD=1 -I viewer -I tools/bots tests/bonus/unlock_host.c $BOTS_LIB viewer/savegame.c -lm -o "$out/red"
"$out/green" "$stage" > "$out/green.log"
if "$out/red" "$stage" > "$out/red.log"; then echo "FAIL old all-open rule not caught"; exit 1; fi
tail -1 "$out/green.log"
tail -1 "$out/red.log"
echo "PASS actual BONUS_UNLOCK_OLD red caught"
