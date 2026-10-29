#!/bin/bash
# Правка 140: продавцы машин уровня 1 в списке персонажей и с моделью рядом (tests/shop/sellers_host.c). Сначала красные:
# -DGAME_PLACE_NPC=0 (прежнее: продавец только лавка) и -DGAME_AMB_SCRIPT_ORDER (модели по порядку скрипта) обязаны упасть;
# потом зелёный.   tests/shop/sellers.sh -> PASS / FAIL
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/shop; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
bad=0
for flag in -DGAME_PLACE_NPC=0 -DGAME_AMB_SCRIPT_ORDER; do
  $CC $flag tests/shop/sellers_host.c $BOTS_LIB -lm -o "$OUT/sellers_red" 2> "$OUT/sellers_build.txt" || { echo "FAIL: сборка $flag"; head -5 "$OUT/sellers_build.txt"; exit 1; }
  if "$OUT/sellers_red" $ARGS > "$OUT/sellers_red.txt" 2>&1; then echo "КРАСНЫЙ $flag НЕ ПОЙМАН"; bad=1
  else echo "красный $flag: $(grep -c 'FAIL' "$OUT/sellers_red.txt") провал(а): $(grep -m1 'CHECK.*FAIL' "$OUT/sellers_red.txt" | cut -c1-110)"; fi
done
$CC tests/shop/sellers_host.c $BOTS_LIB -lm -o "$OUT/sellers" 2> "$OUT/sellers_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/sellers_build.txt"; exit 1; }
echo "зелёный:"; "$OUT/sellers" $ARGS | grep -E "персонажей|CHECK|RESULT"; green=${PIPESTATUS[0]}
[ $bad = 0 ] && [ $green = 0 ] && echo "PASS (красные пойманы, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
