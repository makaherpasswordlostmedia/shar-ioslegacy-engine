#!/bin/bash
# Правка 180: персонажи бонус-миссий на своих местах, как у оригинала (tests/npc/bonus_host.c). Сначала красный:
# -DGAME_BONUS_NPC=0 (прежнее: бонусных в мире нет) обязан упасть; потом зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/npc; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
$CC -DGAME_BONUS_NPC=0 tests/npc/bonus_host.c $BOTS_LIB -lm -o "$OUT/bonus_red" 2> "$OUT/build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/build.txt"; exit 1; }
if "$OUT/bonus_red" $ARGS > "$OUT/bonus_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: прежнее прошло"; red=0
else echo "красный: $(grep -c 'CHECK.*FAIL' "$OUT/bonus_red.txt") провал(а): $(grep -m1 'CHECK.*FAIL' "$OUT/bonus_red.txt" | cut -c1-140)"; red=1; fi
$CC tests/npc/bonus_host.c $BOTS_LIB -lm -o "$OUT/bonus" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
echo "зелёный:"; "$OUT/bonus" $ARGS | grep -E "CHECK|RESULT"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
