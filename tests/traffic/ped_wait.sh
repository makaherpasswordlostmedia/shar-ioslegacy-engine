#!/bin/bash
# tests/traffic/ped_wait.sh [папка уровней] — №692 (причал L3): машина игрока стоит поперёк пешеходного пути 90 с; ни один прохожий не стоит ближе 6 м дольше 2 с.
# Зелёный: PASS; красный (-DPED_WAIT_OLD=1) обязан дать хотя бы одного стоящего дольше 2 с. Папка уровней: l3/level.shr + l3/traffic.shr (по умолчанию build/levels)
set -u
cd "$(dirname "$0")/../.."
L="${1:-build/levels}"; OUT=build/tmp/ped_wait; mkdir -p "$OUT"
SRC="tests/traffic/ped_wait.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c viewer/traffic.c"
cc -std=c11 -O2 -Wno-unused-function -DSKIN_HOST -I viewer $SRC -lm -o "$OUT/green" || exit 2
cc -std=c11 -O2 -Wno-unused-function -DSKIN_HOST -DPED_WAIT_OLD=1 -I viewer $SRC -lm -o "$OUT/red" || exit 2
bad=0
# все отрезки пешеходных путей L3 (178 точек, машина поперёк каждого, 30 с) и полный шаг 1 (449 точек); красный контроль обязан дать скопления
"$OUT/green" "$L/l3/level.shr" "$L/l3/traffic.shr" scan 30 1 | tail -1 | sed "s/^/зелёный: /"; "$OUT/green" "$L/l3/level.shr" "$L/l3/traffic.shr" scan 30 1 > /dev/null || bad=1
"$OUT/red" "$L/l3/level.shr" "$L/l3/traffic.shr" scan 30 3 | tail -1 | sed "s/^/красный: /"; "$OUT/red" "$L/l3/level.shr" "$L/l3/traffic.shr" scan 30 3 > /dev/null && { echo "КРАСНЫЙ НЕ ПОЙМАН"; bad=1; }
"$OUT/green" "$L/l3/level.shr" "$L/l3/traffic.shr" -471.6 -35.3 | sed "s/^/пирс (-471.6; -35.3): /"
[ $bad = 0 ] && echo "ped_wait: зелёный PASS" || echo "ped_wait: FAIL"; exit $bad
