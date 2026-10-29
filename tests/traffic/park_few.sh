#!/bin/bash
# Стоящие машины как у оригинала (TRAFFIC_PARK_FEW_OLD): tests/traffic/park_few.sh [папка уровней, по умолчанию build/levels]. L1 берётся из build/level.shr и build/traffic.shr.
# Зелёный: занято столько мест, сколько моделей пула с флагом стоянки (L1 — 2, как у оригинала). Красный -DTRAFFIC_PARK_FEW_OLD=1 (все места) обязан упасть.
set -u; cd "$(dirname "$0")/../.."
LV="${1:-build/levels}"; O=${TMPDIR:-/tmp}/parkfew.$$; mkdir -p "$O"
SRC="tests/traffic/park_few.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c"
cc -std=c11 -O2 -w -DSKIN_HOST -I viewer $SRC -lm -o $O/green || exit 2
cc -std=c11 -O2 -w -DSKIN_HOST -DTRAFFIC_PARK_FEW_OLD=1 -I viewer $SRC -lm -o $O/old || exit 2
bad=0
for n in 1 2 3 4 5 6 7; do
  if [ $n = 1 ]; then L=build/level.shr; T=build/traffic.shr; else L=$LV/l$n/level.shr; T=$LV/l$n/traffic.shr; fi
  [ -f "$L" ] && [ -f "$T" ] || { echo "L$n: нет данных"; continue; }
  echo "L$n зелёный:"; $O/green $L $T | sed 's/^/  /'; [ ${PIPESTATUS[0]} = 0 ] || bad=1
  echo "L$n прежнее (все места), для сравнения:"; $O/old $L $T 99999 | sed -n 2p | sed 's/^/  /'
  $O/old $L $T > /dev/null && [ $n = 1 ] && { echo "КРАСНЫЙ НЕ ПОЙМАН (L1 прежнее прошло)"; bad=1; }
done
rm -rf $O; [ $bad = 0 ] && echo "park_few: PASS" || echo "park_few: FAIL"; exit $bad
