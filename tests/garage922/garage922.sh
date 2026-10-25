#!/bin/bash
# №922 гейт: спавн в машине у дома (L1, L4, L7), глаз не внутри геометрии. Зелёный — новый код, красный — flag camwallupold 1 (L4 и L7). 5 прогонов параллельно. Использование: garage922.sh [EBOOT]
H=$(cd "$(dirname "$0")" && pwd); B=${1:-$H/../../viewer/build_x/EBOOT.PBP}; export OUT=${OUT:-$H/out}; RUN=${RUN:-$H/../../tools/emu_run.sh}
for t in sp1_n:a1 sp4_n:a4 sp7_n:a7 sp4_o:o4 sp7_o:o7; do bash $RUN $H/${t%%:*}.txt g22_${t##*:} $B 900 >/dev/null 2>&1 & done; wait
rc=0
for L in 1 4 7; do python3 $H/garage922.py $OUT/out_g22_a$L/smoke.txt --scene SP_L$L || rc=1; done
for L in 4 7; do python3 $H/garage922.py $OUT/out_g22_o$L/smoke.txt --scene SP_L$L --expect fail >/dev/null; [ $? = 0 ] && echo "SP_L$L, прежний код: красный (ожидаемо)" || { echo "SP_L$L, прежний код НЕ красный"; rc=1; }; done
[ $rc = 0 ] && echo 'GATE PASS' || echo 'GATE FAIL'; exit $rc
