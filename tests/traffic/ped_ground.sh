#!/bin/bash
# tests/traffic/ped_ground.sh [папка уровней] — правка Роба 594 (L3 D5-9): пешеходы не висят над пустотой (путь без земли под ногами). L3 и L6 (одна карта),
# игрок в точке метки. Зелёный: 0 плохих кадров; красный (-DPED_GROUND_OLD=1) обязан дать их больше нуля.
set -u
cd "$(dirname "$0")/../.."
L="${1:-build/levels}"; OUT=build/tmp/ped_ground; mkdir -p "$OUT"
CC="cc -std=c11 -O2 -Wno-unused-function -DSKIN_HOST -I viewer"
$CC tests/traffic/ped_ground.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c -lm -o "$OUT/green" || exit 2
$CC -DPED_GROUND_OLD=1 tests/traffic/ped_ground.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c -lm -o "$OUT/red" || exit 2
bad=0
for n in 3 6; do
  "$OUT/green" "$L/l$n/level.shr" "$L/l$n/traffic.shr" 90 | tail -1 | sed "s/^/зелёный L$n: /"; "$OUT/green" "$L/l$n/level.shr" "$L/l$n/traffic.shr" 90 > /dev/null || bad=1
  "$OUT/red" "$L/l$n/level.shr" "$L/l$n/traffic.shr" 90 > /dev/null && { echo "КРАСНЫЙ НЕ ПОЙМАН L$n"; bad=1; } || echo "красный контроль L$n (PED_GROUND_OLD=1) упал, как должен"
done
[ $bad = 0 ] && echo "ped_ground: PASS" || echo "ped_ground: FAIL"; exit $bad
