#!/bin/bash
# Правка 240 (Роб 03.10 14:51: «не сбиваются люди вообще никакие»): люди под машиной отлетают — прохожие трафика и персонажи миссий
# (tests/npc/knock_host.c, мир ботов на настоящих данных уровня 1). Сначала красный: -DGAME_NPC_KNOCK=0 -DTR_KNOCK_OLD=1 — прежнее
# (машина проходит сквозь персонажей; прохожий улетает с 0,8 скорости машины и уходит под неё) — обязан упасть; потом зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/npc; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
$CC -DGAME_NPC_KNOCK=0 -DTR_KNOCK_OLD=1 tests/npc/knock_host.c $BOTS_LIB -lm -o "$OUT/knock_red" 2> "$OUT/knock_build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/knock_build.txt"; exit 1; }
if "$OUT/knock_red" $ARGS > "$OUT/knock_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: прежнее прошло"; red=0
else echo "красный: $(grep -c 'CHECK.*FAIL' "$OUT/knock_red.txt") провал(ов), первый: $(grep -m1 'CHECK.*FAIL' "$OUT/knock_red.txt" | cut -c1-200)"; red=1; fi
$CC tests/npc/knock_host.c $BOTS_LIB -lm -o "$OUT/knock" 2> "$OUT/knock_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/knock_build.txt"; exit 1; }
echo "зелёный:"; "$OUT/knock" $ARGS > "$OUT/knock.txt" 2>&1; green=$?; grep -E "CHECK|RESULT|SKIP|ROOM" "$OUT/knock.txt"
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
