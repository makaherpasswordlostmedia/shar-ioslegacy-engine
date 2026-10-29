#!/bin/bash
# Гаечные ключи (tests/wrench/host.c): взять пешком / машиной, починка остова, RESET CAR не чинит, возврат вне вида.
#   tests/wrench/host.sh [LEVEL.shr]            — зелёный прогон (по умолчанию build/level.shr)
#   tests/wrench/host.sh --gate [OLD.shr]       — закон 5: уровень без ключей в данных (OLD, по умолчанию build/level_before_jmp.shr —
#                                                  level.shr до 29.09) обязан упасть, текущий — пройти
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/wrench; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots tests/wrench/host.c $BOTS_LIB -lm \
   -o "$OUT/host" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
if [ "${1:-}" = "--gate" ]; then
  old="${2:-build/level_before_jmp.shr}"; bad=0
  "$OUT/host" "$old" build/homer.shr build/missions/level01.msn > "$OUT/red.txt" 2>&1
  if [ $? -ne 0 ]; then echo "красный (уровень без ключей $old): $(grep -m1 'CHECK data' "$OUT/red.txt" | cut -c1-120)"; else echo "КРАСНЫЙ НЕ ПОЙМАН"; bad=1; fi
  "$OUT/host" build/level.shr build/homer.shr build/missions/level01.msn > "$OUT/green.txt" 2>&1 || bad=1
  grep "^CHECK\|^RESULT" "$OUT/green.txt"
  [ $bad = 0 ] && echo "wrench gate: PASS" || echo "wrench gate: FAIL"; exit $bad
fi
"$OUT/host" "${1:-build/level.shr}" build/homer.shr build/missions/level01.msn
