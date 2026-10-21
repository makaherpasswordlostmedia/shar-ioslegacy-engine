#!/bin/bash
# Кошелёк и продавцы (tests/shop/host.c) + m3 миссионером: этап «купи Plow King у Барни» пройден покупкой.
#   tests/shop/host.sh           — зелёный прогон
#   tests/shop/host.sh --gate    — закон 5: сначала красные (сборка без кошелька рантайма -DGAME_SHOP_API=0; m3 без монет;
#                                  рантайм без пар-времени -DMSN_BREAK_PARTIME=1 — gr1_par),
#                                  потом зелёные; итог «shop gate: PASS/FAIL»
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/shop; mkdir -p "$OUT"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots"
ARGS="build/level.shr build/homer.shr build/missions/level01.msn"
$CC tests/shop/host.c $BOTS_LIB -lm -o "$OUT/host" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
m3() {   # $1 монет на старте -> 0, если этап покупки пройден (миссионер дошёл до основной части m3)
  build/bots/missioner build/level.shr build/homer.shr build/sandbox/roads-l1.bin build/missions/level01.msn --mission 3 --coins "$1" --secs 150 -v 2>/dev/null > "$OUT/m3_$1.txt"
  grep -q "стадия 1.0 " "$OUT/m3_$1.txt"
}
BINS=missioner tools/bots/build.sh > /dev/null 2>&1 || { echo "FAIL: сборка миссионера"; exit 1; }
if [ "${1:-}" = "--gate" ]; then
  bad=0
  $CC -DGAME_SHOP_API=0 tests/shop/host.c $BOTS_LIB -lm -o "$OUT/host_noapi" 2>> "$OUT/build.txt" || { echo "FAIL: сборка красного"; exit 1; }
  "$OUT/host_noapi" $ARGS > "$OUT/red_noapi.txt" 2>&1
  if [ $? -ne 0 ] && grep -q "gr1 .*FAIL" "$OUT/red_noapi.txt"; then echo "красный 1 (без кошелька рантайма): $(grep 'gr1 ' "$OUT/red_noapi.txt" | cut -c1-140)"
  else echo "КРАСНЫЙ 1 НЕ ПОЙМАН"; bad=1; fi
  $CC -DGAME_SHOP_ATTR=0 tests/shop/host.c $BOTS_LIB -lm -o "$OUT/host_noattr" 2>> "$OUT/build.txt" || { echo "FAIL: сборка красного 3"; exit 1; }
  "$OUT/host_noattr" $ARGS > "$OUT/red_noattr.txt" 2>&1
  if [ $? -ne 0 ] && grep -q "stars .*FAIL" "$OUT/red_noattr.txt"; then echo "красный 3 (без SetCarAttributes): $(grep 'stars ' "$OUT/red_noattr.txt" | cut -c1-120)"
  else echo "КРАСНЫЙ 3 НЕ ПОЙМАН"; bad=1; fi
  # красный 4 (часть race 30.09): рантайм без пар-времени -DMSN_BREAK_PARTIME=1 — опоздавший на гонке-ставке gr1 забирает выигрыш
  $CC -DMSN_BREAK_PARTIME=1 tests/shop/host.c $BOTS_LIB -lm -o "$OUT/host_nopar" 2>> "$OUT/build.txt" || { echo "FAIL: сборка красного 4"; exit 1; }
  "$OUT/host_nopar" $ARGS > "$OUT/red_nopar.txt" 2>&1
  if [ $? -ne 0 ] && grep -q "gr1_par .*FAIL" "$OUT/red_nopar.txt"; then echo "красный 4 (без пар-времени): $(grep 'gr1_par ' "$OUT/red_nopar.txt" | cut -c1-150)"
  else echo "КРАСНЫЙ 4 НЕ ПОЙМАН"; bad=1; fi
  if m3 0; then echo "КРАСНЫЙ 2 НЕ ПОЙМАН: m3 без монет прошёл покупку"; bad=1
  else echo "красный 2 (m3, 0 монет): этап покупки не пройден — $(grep -m1 '^M' "$OUT/m3_0.txt" | cut -f5,6)"; fi
  "$OUT/host" $ARGS > "$OUT/green.txt" 2>&1; rc=$?; grep "^CHECK\|^RESULT" "$OUT/green.txt"; [ $rc = 0 ] || bad=1
  if m3 200; then echo "m3 (200 монет): Plow King куплен, дальше основная часть — $(grep -m1 'стадия 1.0' "$OUT/m3_200.txt" | cut -c1-60)"
  else echo "m3 (200 монет): этап покупки НЕ пройден"; bad=1; fi
  [ $bad = 0 ] && echo "shop gate: PASS" || echo "shop gate: FAIL"; exit $bad
fi
"$OUT/host" $ARGS; rc=$?
m3 200 && echo "m3: покупка пройдена" || { echo "m3: покупка не пройдена"; rc=1; }
exit $rc
