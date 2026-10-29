#!/bin/bash
# Гейт 905 (L1 H4-6, «невидимое препятствие после прыжка с трамплина»): машина в полёте (X −Y 74,7/−334, курс на север, 18 м/с, высота 9 м) над ямой у подножия горы
# не должна упираться в звено забора с верхом +1e6 (сегмент 1688). usage: tests/walls905/airwall.sh NEW_level.shr OLD_level.shr
# новое — обязано пройти (rc 0), старое — обязано упереться (rc 1, красный контроль). Только COL1, на Маке.
set -e
D=$(cd "$(dirname "$0")" && pwd); R=$(cd "$D/../.." && pwd); T=$(mktemp -d)
cc -O1 -w -DCOL_DEBUG -I"$R/viewer" -o "$T/air" "$R/tools/cartest/airwall905.c" "$R/viewer/col.c" "$R/viewer/car.c" -lm
set +e
"$T/air" "$1" 74.7 -334 3.1416 18 9 2; rn=$?
"$T/air" "$2" 74.7 -334 3.1416 18 9 2; ro=$?
set -e
echo "новое rc=$rn (ждём 0), старое rc=$ro (ждём 1)"
[ "$rn" = 0 ] && [ "$ro" = 1 ] && echo "PASS 905" || { echo "FAIL 905"; exit 1; }
