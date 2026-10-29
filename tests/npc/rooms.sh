#!/bin/bash
# Правка 171: фоновые персонажи в комнатах (Апу, Лиза) получают модель рядом с Гомером (tests/npc/rooms_host.c). Сначала
# красный: -DGAME_AMB_TAG_ONLY (прежний отбор по имени интерьера, правка 140) обязан упасть; потом зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/npc; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
$CC -DGAME_AMB_TAG_ONLY tests/npc/rooms_host.c $BOTS_LIB -lm -o "$OUT/rooms_red" 2> "$OUT/build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/build.txt"; exit 1; }
if "$OUT/rooms_red" $ARGS > "$OUT/red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: прежний отбор прошёл"; red=0
else echo "красный: $(grep -c 'CHECK.*FAIL' "$OUT/red.txt") провал(а): $(grep -m1 'CHECK.*FAIL' "$OUT/red.txt" | cut -c1-120)"; red=1; fi
$CC tests/npc/rooms_host.c $BOTS_LIB -lm -o "$OUT/rooms" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
echo "зелёный:"; "$OUT/rooms" $ARGS | grep -E "CHECK|RESULT"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
