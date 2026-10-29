#!/bin/bash
# №923 гейт: перенос на ~960 м (L2 repair), кадр правила глаза ≤ 50 мс; красный — flag camxferold 1. Использование: xfer923.sh [EBOOT]
H=$(cd "$(dirname "$0")" && pwd); B=${1:-$H/../../viewer/build_x/EBOOT.PBP}; export OUT=${OUT:-$H/out}; RUN=$H/../eyejump/run.sh
bash $RUN $H/xfer_n.txt x23n $B 900 >/dev/null 2>&1 & bash $RUN $H/xfer_o.txt x23o $B 900 >/dev/null 2>&1 & wait
rc=0; python3 $H/xfer923.py $OUT/out_x23n/smoke.txt || rc=1
python3 $H/xfer923.py $OUT/out_x23o/smoke.txt --expect fail >/dev/null; [ $? = 0 ] && echo 'прежний код: красный (ожидаемо)' || { echo 'прежний код НЕ красный'; rc=1; }
[ $rc = 0 ] && echo 'GATE PASS' || echo 'GATE FAIL'; exit $rc
