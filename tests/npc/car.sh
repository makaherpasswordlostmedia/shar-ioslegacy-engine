#!/bin/bash
# Правка 217: персонаж миссии обходит машину игрока, а не идёт сквозь кузов (tests/npc/car_host.c). Сначала красный
# -DGAME_NPC_CAR_AVOID=0 (прежнее: сквозь кузов) обязан упасть, потом зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/npc; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
$CC -DGAME_NPC_CAR_AVOID=0 tests/npc/car_host.c $BOTS_LIB -lm -o "$OUT/car_red" 2> "$OUT/car_build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/car_build.txt"; exit 1; }
if "$OUT/car_red" $ARGS > "$OUT/car_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; else echo "красный: $(grep 'курс' "$OUT/car_red.txt")"; red=1; fi
$CC tests/npc/car_host.c $BOTS_LIB -lm -o "$OUT/car" 2> "$OUT/car_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/car_build.txt"; exit 1; }
"$OUT/car" $ARGS | tail -2; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
