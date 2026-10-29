#!/bin/bash
# Правка 219: персонаж миссии идёт по полу, а не к высоте точки маршрута (tests/npc/lisa_host.c). Сначала красный
# -DGAME_NPC_WP_Y=1 (прежнее: высота к точке) обязан упасть, потом зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/npc; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
$CC -DGAME_NPC_WP_Y=1 tests/npc/lisa_host.c $BOTS_LIB -lm -o "$OUT/lisa_red" 2> "$OUT/lisa_build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/lisa_build.txt"; exit 1; }
if "$OUT/lisa_red" $ARGS > "$OUT/lisa_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; else echo "красный: $(grep 'Лиза' "$OUT/lisa_red.txt")"; red=1; fi
$CC tests/npc/lisa_host.c $BOTS_LIB -lm -o "$OUT/lisa" 2> "$OUT/lisa_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/lisa_build.txt"; exit 1; }
"$OUT/lisa" $ARGS | tail -2; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
