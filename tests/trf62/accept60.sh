#!/bin/bash
# №930в «Мультик»: цена трафика в туре.   tests/trf62/accept60.sh      (последняя строка: PASS или FAIL)
#   Что делает: три сборки тура (новая; красная CFCOST_OLD=1 = как test62, замеры читают время ядра 4 раза на кусок; база CARFILL930_OLD=1 = как до заливки), фиксированная сцена L5 (одна машина трафика стоит в 7 м, вокруг ещё ~3,
#   заливка включается и выключается окнами по 7 с), цена на машину из PHSUB trf_cars. Эмулятор считает одинаково при повторе (одни и те же числа)
#   Зелёное: (1) новая не дороже красной × 0,95; (2) заливка включена не дороже базы без заливки × 1,03; (3) «flag cfcost 1» возвращает CFCOST (отрисовок > 500), без флага нули.
#   Красные: новая со «flag cfcost 1» с начала прогона (замеры вернулись) обязана упасть на (1)
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test61tour/PSP/GAME/SHARTEST15}; export EMU_OWNER=${EMU_OWNER:-Мультик} EMU_MINE=${EMU_MINE:-2}
A=${A:-$W/build/trf62/accept}; mkdir -p "$A"; BAD=0; F="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
for v in "t62:" "t62_red:-DCFCOST_OLD=1" "t62_base:-DCARFILL930_OLD=1"; do n=${v%%:*}; x=${v#*:}
  ( cd viewer && psp-cmake -S . -B build_$n -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$F $x" > "$A/cfg_$n.log" 2>&1 && cmake --build build_$n -j4 > "$A/b_$n.log" 2>&1 ); [ -f viewer/build_$n/EBOOT.PBP ] || bad "нет сборки $n"; done
S=tests/trf62/scenario_fixed.txt; awk 'NR==1{print; print "flag cfcost 1"; next} {print}' $S > "$A/scenario_cfc.txt"
run() { OUT="$A" tools/emu_run.sh "$1" "$2" "$3" "${4:-900}" > "$A/$2.log" 2>&1; }
( run $S new viewer/build_t62/EBOOT.PBP & run $S red viewer/build_t62_red/EBOOT.PBP & wait )
( run $S base viewer/build_t62_base/EBOOT.PBP & run "$A/scenario_cfc.txt" newc viewer/build_t62/EBOOT.PBP & wait )
run tests/trf62/cfcost.txt cfc viewer/build_t62/EBOOT.PBP 600
C="python3 tests/trf62/check.py"; O=$A/out_
echo "-- (1) цена трафика без замеров CFCOST"; $C gate ${O}new/smoke.txt ${O}red/smoke.txt 0.95 && ok "новая не дороже красной × 0,95" || bad "(1) не прошло"
$C gate ${O}newc/smoke.txt ${O}red/smoke.txt 0.95 > /dev/null 2>&1 && bad "красный контроль: замеры вернулись, а гейт прошёл" || ok "красный контроль (замеры включены флагом) упал, как должен"
echo "-- (2) заливка не дороже базы"; $C fill ${O}new/smoke.txt ${O}base/smoke.txt 1.03 && ok "заливка не дороже" || bad "(2) не прошло"
echo "-- (3) CFCOST по флагу"; $C cfc ${O}cfc/smoke.txt ${O}new/smoke.txt && ok "CFCOST по флагу" || bad "(3) не прошло"
[ $BAD = 0 ] && echo PASS || echo FAIL
