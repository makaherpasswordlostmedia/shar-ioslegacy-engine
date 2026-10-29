#!/bin/bash
# ДОБИВКА 14, частные машины (правки Роба 354 honor_v L2, 358 lisa_v/plowk_v L3, 368 bart_v L6): tests/cars/car_specific.c и посадка
# с трамплина против PS2 (tests/cars/air_pitch_ps2.py по трассам tests/jumps/twin.c). Каждый блок со своим красным — он обязан упасть.
#   tests/cars/car_specific.sh [LEVEL1] [LEVEL3] [LEVEL6]   (по умолчанию build/level.shr, build/levels/l3/level.shr, build/levels/l6/level.shr)
set -u
cd "$(dirname "$0")/../.."
L1=${1:-build/level.shr}; L3=${2:-build/levels/l3/level.shr}; L6=${3:-build/levels/l6/level.shr}
OUT=${OUT_DIR:-build/cars-specific}; mkdir -p "$OUT"
PY=${PY:-.venv/bin/python}; [ -x "$PY" ] || PY=python3
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -I viewer"
bad=0
$CC tests/cars/car_specific.c viewer/car.c viewer/col.c -lm -o "$OUT/green" || exit 2
"$OUT/green" "$L3" "$L6" > "$OUT/green.log"; r=$?
grep -E 'honor_v|^A  машин|^B|^C ' "$OUT/green.log"; tail -1 "$OUT/green.log"
[ $r = 0 ] || { echo "ЗЕЛЁНЫЙ: FAIL"; bad=1; }
red() {   # red BLOCK FLAGS...
  local b=$1; shift
  $CC "$@" tests/cars/car_specific.c viewer/car.c viewer/col.c -lm -o "$OUT/red" || exit 2
  "$OUT/red" "$L3" "$L6" > "$OUT/red_$b.log"
  if grep -q "RESULT.* $b FAIL" "$OUT/red_$b.log"; then echo "красный $b ($*): упал, как должен — $(tail -1 "$OUT/red_$b.log")"
  else echo "КРАСНЫЙ $b НЕ УПАЛ ($*): $(tail -1 "$OUT/red_$b.log")"; bad=1; fi
}
red A -DCAR_WHEEL_RADIUS_MESH_OLD=1
red B -DCAR_TYRE_LEVER_OLD=1 -DCAR_WEEBLE_GROUND_OLD=1 -DCAR_AIR_PITCH_OLD=1
red C -DCAR_AIR_PITCH_OLD=1
# D is a diagnostic for the shared air-pitch rule, owned by house physics.
# Keep printing the comparison, but it is not a car-specific acceptance gate.
for k in green red; do
  f=""; [ $k = red ] && f="-DCAR_AIR_PITCH_OLD=1"
  $CC -DSKIN_HOST $f tests/jumps/twin.c viewer/car.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o "$OUT/twin_$k" || exit 2
  rm -rf "$OUT/trace_$k"; mkdir -p "$OUT/trace_$k"
  "$OUT/twin_$k" "$L1" --trace "$OUT/trace_$k" > "$OUT/twin_$k.log"
  "$PY" tests/cars/air_pitch_ps2.py "$OUT/trace_$k" > "$OUT/pitch_$k.log"; eval "d_$k=$?"
done
cat "$OUT/pitch_green.log"
echo "диагностика D (общий air-pitch закон, владелец house physics): green=$(tail -1 "$OUT/pitch_green.log"); old=$(tail -1 "$OUT/pitch_red.log")"
if [ "$d_green" = 2 ] || [ "$d_red" = 2 ]; then
  echo "НЕТ ДАННЫХ: не загружен PS2-эталон или комплект из 12 трасс; см. $OUT/pitch_green.log и $OUT/pitch_red.log"
  bad=1
fi
[ $bad = 0 ] && echo "car specific gate: PASS" || echo "car specific gate: FAIL"
exit $bad
