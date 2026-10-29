#!/bin/bash
# №418: машины мира уровней 1–7 (tests/msncars/freecars.c). Данные: build/level.shr (+msncars-l1.shr), build/levels/l<N>/.
#   tests/msncars/freecars.sh          — зелёный прогон
#   tests/msncars/freecars.sh --gate   — красные: -DWORLD_CARS_OLD (до №418 — только ракетная L1) и -DWORLD_CAR_SPOT_OLD обязаны упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/freecars; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
ARGS=(build/homer.shr build/level.shr build/missions/level01.msn)
for n in 2 3 4 5 6 7; do d=build/levels/l$n; [ -f $d/level.shr ] && ARGS+=($d/level.shr $d/level0$n.msn); done
mk() { cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST $1 -I $V -I tools/bots tests/msncars/freecars.c $BOTS_LIB -lm -o "$2" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }; }
mk "" "$OUT/host"
if [ "${1:-}" = "--gate" ]; then
  mk -DWORLD_CARS_OLD "$OUT/host_old"; bad=0
  "$OUT/host_old" "${ARGS[@]}" > "$OUT/red.txt" 2>&1
  if [ $? -ne 0 ]; then echo "красный (WORLD_CARS_OLD): $(grep -c 'FAIL ' "$OUT/red.txt") FAIL, первый: $(grep -m1 'FAIL ' "$OUT/red.txt" | cut -c1-160)"; else echo "КРАСНЫЙ НЕ ПОЙМАН"; bad=1; fi
  mk -DWORLD_CAR_SPOT_OLD "$OUT/host_spot"   # второй красный: опора до 2.5 м над локатором (L6 hype_v на карнизе, съезд 4.7 м)
  "$OUT/host_spot" "${ARGS[@]}" > "$OUT/red_spot.txt" 2>&1
  if [ $? -ne 0 ]; then echo "красный (WORLD_CAR_SPOT_OLD): $(grep -m1 'FAIL ' "$OUT/red_spot.txt" | cut -c1-160)"; else echo "КРАСНЫЙ 2 НЕ ПОЙМАН"; bad=1; fi
  "$OUT/host" "${ARGS[@]}" > "$OUT/green.txt" 2>&1 || bad=1
  grep "^CHECK\|^RESULT" "$OUT/green.txt"
  [ $bad = 0 ] && echo "freecars gate: PASS" || echo "freecars gate: FAIL"; exit $bad
fi
"$OUT/host" "${ARGS[@]}"
