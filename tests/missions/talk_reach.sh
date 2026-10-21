#!/bin/bash
# Правка 345: дальность разговора △ с персонажем миссии — как у оригинала (tests/missions/talk_reach_host.c): 4-й аргумент
# SetTalkToTarget — радиус, без него 1,3 м, без запаса. Сначала красный: --old (msnTalkOld = 1, прежнее 3 м + 1 м) обязан упасть;
# потом зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/talk_reach; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions"
$CC tests/missions/talk_reach_host.c $BOTS_LIB -lm -o "$OUT/talk_reach" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
if "$OUT/talk_reach" $ARGS --old > "$OUT/red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: прежнее прошло"; red=0
else echo "красный (--old): $(grep -c 'CHECK.*FAIL' "$OUT/red.txt") провал(а): $(grep -m1 'CHECK.*FAIL' "$OUT/red.txt" | cut -c1-160)"; grep INFO "$OUT/red.txt"; red=1; fi
echo "зелёный:"; "$OUT/talk_reach" $ARGS | grep -E "CHECK|INFO|RESULT"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
