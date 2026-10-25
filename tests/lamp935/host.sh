#!/bin/bash
# Гейт №935: у ламп на мосту и эстакаде эллипса света на полу нет, конус остаётся. Все семь уровней, настоящие данные (SPR1 -> таблица света, COL1), то же правило lpPoolSkip, что в игре.
#   tests/lamp935/host.sh [НАБОР]   НАБОР — папка с level.shr и l2..l7/level.shr (по умолчанию build/botset), HOMER — НАБОР/../homer.shr или build/homer.shr (HOMER=файл)
# На каждом уровне: зелёный — все лампы на мосту (вторая поверхность глубже 3 м) без эллипса, не на мосту без эллипса не больше 15 %; красный (-DLAMP_POOL_BRIDGE_OLD=1) обязан упасть там, где лампы на мосту найдены.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; V=viewer; . tools/bots/lib.sh
SET=${1:-build/botset}; HM=${HOMER:-build/homer.shr}; OUT=build/lamp935; mkdir -p "$OUT"
CC="cc -std=c11 -O2 -w -DSKIN_HOST -I $V -I tools/bots"
$CC -DLAMP_POOL_BRIDGE_OLD=1 tests/lamp935/host.c $BOTS_LIB -lm -o "$OUT/red" || { echo "FAIL: сборка красного"; exit 1; }
$CC tests/lamp935/host.c $BOTS_LIB -lm -o "$OUT/green" || { echo "FAIL: сборка"; exit 1; }
fail=0; total=0
for L in 1 2 3 4 5 6 7; do
  if [ $L = 1 ]; then f="$SET/level.shr"; else f="$SET/l$L/level.shr"; fi
  [ -f "$f" ] || { echo "L$L: нет $f — пропуск"; continue; }
  "$OUT/green" "$f" "$HM" 0 0 1 > "$OUT/green_L$L.txt" 2>&1; g=$?; "$OUT/red" "$f" "$HM" 0 0 1 > "$OUT/red_L$L.txt" 2>&1; r=$?
  n=$(sed -n 's/^FOUND \([0-9]*\)/\1/p' "$OUT/green_L$L.txt"); n=${n:-0}; total=$((total + n))
  if [ $g != 0 ]; then echo "L$L: ЗЕЛЁНЫЙ УПАЛ — $(grep -m1 'CHECK.*FAIL' "$OUT/green_L$L.txt" | cut -c1-140)"; fail=1
  elif [ "$n" -gt 0 ] && [ $r = 0 ]; then echo "L$L: КРАСНЫЙ НЕ ПОЙМАН (ламп на мосту $n)"; fail=1
  elif [ "$n" -gt 0 ]; then echo "L$L: ламп на мосту $n — зелёный сошёлся, красный упал, как должен"
  else echo "L$L: ламп на мосту нет (красный проверять нечем), город не тронут — зелёный сошёлся"; fi
done
[ $total -ge 10 ] || { echo "FAIL: на всех уровнях найдено только $total ламп на мосту"; fail=1; }
[ $fail = 0 ] && echo "PASS (ламп на мосту по уровням: $total)" || echo "FAIL"
exit $fail
