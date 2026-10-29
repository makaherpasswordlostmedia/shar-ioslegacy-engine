#!/bin/bash
# №930г «Мультик»: город стоя не дорожает от слияния №930.   tests/city930/accept60.sh      (последняя строка: PASS или FAIL)
#   Три сборки тура: новая; красная THQ930D_OLD=1 (очередь контура 56 мест, как test62); база CARFILL930_OLD=1 (как до №930). Сцена: L4 и L7 стоя (tests/city930/scenario.txt), окна по 10 с, x_city из PHSEC (эмулятор повторяет числа).
#   Зелёное: x_city новой не выше базы больше чем на 0,02 мс Мак (≈ 0,12 PSP) на L4 и L7. Красное: красная сборка обязана упасть (в ней на L4 +0,14 Мак).
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test61tour/PSP/GAME/SHARTEST15}; export EMU_OWNER=${EMU_OWNER:-Мультик} EMU_MINE=${EMU_MINE:-2}
A=${A:-$W/build/c930/accept}; mkdir -p "$A"; BAD=0; F="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
for v in "new:" "red:-DTHQ930D_OLD=1" "base:-DCARFILL930_OLD=1"; do n=${v%%:*}; x=${v#*:}
  ( cd viewer && psp-cmake -S . -B build_c_$n -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$F $x" > "$A/cfg_$n.log" 2>&1 && cmake --build build_c_$n -j4 > "$A/b_$n.log" 2>&1 ); [ -f viewer/build_c_$n/EBOOT.PBP ] || bad "нет сборки $n"; done
run() { OUT="$A" tools/emu_run.sh tests/city930/scenario.txt "$1" "$2" 900 > "$A/$1.log" 2>&1; }
( run new viewer/build_c_new/EBOOT.PBP & run red viewer/build_c_red/EBOOT.PBP & wait ); run base viewer/build_c_base/EBOOT.PBP
C="python3 tests/city930/check.py"; O=$A/out_
echo "-- новая против базы"; $C gate ${O}new/smoke.txt ${O}base/smoke.txt 0.02 && ok "город стоя как до №930" || bad "новая дороже базы"
$C gate ${O}red/smoke.txt ${O}base/smoke.txt 0.02 > "$A/red.txt" 2>&1 && bad "красный контроль: сборка с 56 местами прошла гейт" || ok "красный контроль (56 мест) упал, как должен"
[ $BAD = 0 ] && echo PASS || echo FAIL
