#!/bin/bash
# №417: гаечные ключи уровней 1–7 подряд в одной сессии (tests/wrench/levels.c). Данные: build/level.shr + build/ship_stage/l<N>/.
#   tests/wrench/levels.sh            — зелёный прогон
#   tests/wrench/levels.sh --gate     — красный контроль: сборка с -DWRENCH_REMAP_OLD (прежнее разовое сопоставление) обязана упасть
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/wrench; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
ARGS=(build/homer.shr build/level.shr build/missions/level01.msn)
for n in 2 3 4 5 6 7; do d=build/ship_stage/l$n; [ -f $d/level.shr ] && ARGS+=($d/level.shr $d/level0$n.msn); done
mk() { cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST $1 -I $V -I tools/bots tests/wrench/levels.c $BOTS_LIB -lm -o "$2" 2> "$OUT/build_levels.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build_levels.txt"; exit 1; }; }
mk "" "$OUT/levels"
if [ "${1:-}" = "--gate" ]; then
  mk -DWRENCH_REMAP_OLD "$OUT/levels_old"; bad=0
  "$OUT/levels_old" "${ARGS[@]}" > "$OUT/levels_red.txt" 2>&1
  if [ $? -ne 0 ]; then echo "красный (WRENCH_REMAP_OLD): $(grep -m1 'FAIL' "$OUT/levels_red.txt" | cut -c1-200)"; else echo "КРАСНЫЙ НЕ ПОЙМАН"; bad=1; fi
  "$OUT/levels" "${ARGS[@]}" > "$OUT/levels_green.txt" 2>&1 || bad=1
  grep "^CHECK\|^RESULT" "$OUT/levels_green.txt"
  [ $bad = 0 ] && echo "wrench levels gate: PASS" || echo "wrench levels gate: FAIL"; exit $bad
fi
"$OUT/levels" "${ARGS[@]}"
