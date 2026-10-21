#!/bin/bash
# Правки Роба 46–47 на Маке (tests/jumps/host.c): перелёт дома с трамплина jumpzone17 и подкидывающие точки Гомера.
#   tests/jumps/host.sh [level.shr] [homer.shr] [--no-boost|--old47|--plant-wall|--no-pads] [--routes routes-l1.tsv] [-v]
#   tests/jumps/host.sh --gate [level.shr]   — гейт: как есть PASS, каждый отрицательный контроль FAIL (закон 5)
set -u
cd "$(dirname "$0")/../.."
out=build/tmp/jumps-host; mkdir -p build/tmp
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/jumps/host.c viewer/car.c viewer/col.c viewer/homer.c \
  viewer/skin.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o "$out" || exit 2
if [ "${1:-}" = "--gate" ]; then
  lvl="${2:-build/level.shr}"; bad=0
  "$out" "$lvl" > build/tmp/jumps-ok.txt; r=$?; tail -1 build/tmp/jumps-ok.txt
  [ $r = 0 ] || { echo "гейт: как есть — FAIL"; bad=1; }
  # --no-boost с правки 342 не контроль: машина, уже идущая 100 км/ч за 40 м до кромки, перелетает дом и без разгона зоны,
  # как и у оригинала; разгон зоны «jump boost» проверяет tests/jumps/twin.sh --gate (контроль --no-drive)
  for k in --old47 --plant-wall --no-pads; do
    "$out" "$lvl" $k > build/tmp/jumps$k.txt; r=$?
    echo "контроль $k: $(tail -1 build/tmp/jumps$k.txt)"
    [ $r != 0 ] || { echo "гейт: контроль $k не покраснел"; bad=1; }
  done
  # правка 45: без шагов бега (как до правки: пыли при беге нет) — проверка 4 обязана упасть
  cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -DHOMER_STEP_DUST=0 -I viewer tests/jumps/host.c viewer/car.c viewer/col.c viewer/homer.c \
    viewer/skin.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o "$out-nostep" || exit 2
  "$out-nostep" "$lvl" > build/tmp/jumps-nostep.txt; r=$?
  echo "контроль -DHOMER_STEP_DUST=0: $(grep -m1 '4. пыль' build/tmp/jumps-nostep.txt | cut -c1-110)"
  if [ $r = 0 ] || ! grep -q "^FAIL 4. пыль: клубов на шаги бега" build/tmp/jumps-nostep.txt; then echo "гейт: контроль без шагов не покраснел"; bad=1; fi
  [ $bad = 0 ] && echo "jumps gate: PASS" || echo "jumps gate: FAIL"; exit $bad
fi
"$out" "$@"
