#!/bin/bash
# №946 приёмка: сбиваемые столбы падают, а не едут стоймя перед машиной (тяжёлый высокий предмет падал со скоростью ~1/высота рад/с, машина-«бульдозер» гнала его 25–70 м).
# Аргумент 1 — EBOOT тура (сборка по наряду TEST61). Часть 1 — перепись на хосте (census.c: настоящие car/col/props на данных L7 и L2, 4 курса на предмет), часть 2 — заезд в эмуляторе.
# Красный контроль — прежнее поведение: POLE968OLD=1 (перепись) / flag pole968old 1 (эмулятор); обязан дать «не годится».
H=$(cd "$(dirname "$0")" && pwd); W=$H/../..; E=${1:?EBOOT}; OUT=${OUT:-$H/out}; mkdir -p $OUT; export EMU_OWNER=${EMU_OWNER:-Управление} EMU_MINE=${EMU_MINE:-2} OUT; rc=0
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk}
cc -std=c11 -O2 -w -DSKIN_HOST -I $W/viewer -o $OUT/census $H/census.c $W/viewer/col.c $W/viewer/props.c $W/viewer/stateprops.c $W/viewer/car.c $W/viewer/coins.c -lm || { echo "census не собрался"; echo FAIL; exit 1; }
awk '{print} /^flag repair/ && !d {print "flag pole968old 1"; d=1}' $H/l7_tilt.txt > $OUT/l7_tilt_red.txt
bash $W/tools/emu_run.sh $H/l7_tilt.txt n $E 300 >/dev/null 2>&1 & bash $W/tools/emu_run.sh $OUT/l7_tilt_red.txt o $E 300 >/dev/null 2>&1 &
for L in 7 2; do $OUT/census $SET/l$L/level.shr P > $OUT/P${L}_new.txt; POLE968OLD=1 $OUT/census $SET/l$L/level.shr P > $OUT/P${L}_old.txt
  echo "== L$L перепись, новый код"; python3 $H/check_census.py $OUT/P${L}_new.txt || rc=1
  echo "== L$L перепись, красный (прежнее падение)"; python3 $H/check_census.py $OUT/P${L}_old.txt --expect fail || { echo "КРАСНЫЙ КОНТРОЛЬ НЕ КРАСНЫЙ"; rc=1; }; done
wait
echo "== игра (эмулятор), новый код"; python3 $H/check_game.py $OUT/out_n/smoke.txt || rc=1
echo "== игра (эмулятор), красный (flag pole968old 1)"; python3 $H/check_game.py $OUT/out_o/smoke.txt --expect fail || { echo "КРАСНЫЙ КОНТРОЛЬ НЕ КРАСНЫЙ"; rc=1; }
[ $rc = 0 ] && echo "PASS" || echo "FAIL"; exit $rc
