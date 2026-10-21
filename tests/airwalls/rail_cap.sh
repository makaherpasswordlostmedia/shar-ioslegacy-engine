#!/bin/bash
# Правка 164б/187 (F12-6 правые перила, «невидимый столб»): коллизия ножки перил ящиков 72/73 уже видимой полки на 0,2 м и на стыке с ящиком 69 (z 457,4)
# образует уступ; колесо бьётся о торец. Экспорт col_rail_caps (RAIL_CAP_COL_OLD=1 — без него) добавляет ящик полки по видимой ширине.
# Гейт: машина брошена как в crash.sh (F12-6R); на z 461 скорость >= 12 м/с (PS2 по v22_f126r: 14,5) и она не стоит раньше (z_конца >= 462);
# красный — уровень, экспортированный с RAIL_CAP_COL_OLD=1: упирается до z 459, скорость на z 461 нет.
#   tests/airwalls/rail_cap.sh LEVEL_NEW.shr LEVEL_OLD.shr
set -u; cd "$(dirname "$0")/../.."; NEW=${1:?}; OLD=${2:?}; T=${TMPDIR:-/tmp}/rail_cap.$$
cc -std=c11 -O2 -w -DSKIN_HOST -I viewer tests/airwalls/host.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o "$T.b" || exit 2
meas() { AW_VHEAD=0 "$T.b" "$1" drop -114 8.235 452 7.4 18 1 2 2 2>&1 | awk '/^t=/ { z = $5 + 0; i = index($0, "|v| "); a[2] = substr($0, i + 4); split(a[2], b, "->"); if (z >= 461 && !got) { v = b[2] + 0; got = 1 } } /^SUMMARY/ { end = $5 } END { printf "%.1f %.1f\n", got ? v : 0, end }'; }
read -r vn en <<< "$(meas "$NEW")"; read -r vo eo <<< "$(meas "$OLD")"
echo "полка (новый экспорт): скорость на z 461 = $vn м/с, конец z = $en"; echo "красный (RAIL_CAP_COL_OLD=1): скорость на z 461 = $vo м/с, конец z = $eo"
rm -f "$T.b"
ok=$(awk -v vn="$vn" -v en="$en" -v vo="$vo" -v eo="$eo" 'BEGIN{print (vn >= 12 && en >= 462 && vo < 6 && eo < 459) ? 1 : 0}')
[ "$ok" = 1 ] && { echo "rail_cap: PASS"; exit 0; }; echo "rail_cap: FAIL"; exit 1
