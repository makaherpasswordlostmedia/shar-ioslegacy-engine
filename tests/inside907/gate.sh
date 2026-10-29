#!/bin/bash
# №907 гейт «предметы изнанкой» (автомат с газировкой и всё семейство: пропы и стейтпропы с пустым смешиванием).
# Использование: gate.sh NEW_EBOOT OLD_EBOOT   (RUN — безголовый раннер, по умолчанию tools/emu_run.sh; SET — набор данных; подмена level.shr идёт папкой-наложением OVL)
#  1) перепись по level.shr всех уровней набора: кусков с пустым смешиванием (должно быть > 0 — свойство данных диска)
#  2) картинки орбиты у автомата L1 (АЭС, -46 -303): OLD на данных диска, TRUTH = OLD на данных с флагом, снятым в файле, NEW на данных диска
#  3) журнал движка NEW: BLENDOPQ pieces == перепись L1
# Красный контроль: gate.sh OLD_EBOOT OLD_EBOOT -> FAIL (нет строки BLENDOPQ, картинка как у OLD)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/inside907
NEW=$1; OLD=$2; W=${W:-$ROOT/build/gates/gate907}; export OUT=$W; rm -rf $W; mkdir -p $W/ref $W/ovl; fail=0
echo "--- 1) перепись данных (L1..L7)"
$PY $T/census.py $SET/level.shr $SET/l2/level.shr $SET/l3/level.shr $SET/l4/level.shr $SET/l5/level.shr $SET/l6/level.shr $SET/l7/level.shr | tee $W/census.txt | sed 's/^.*SHARTEST15\//  /' | cut -c1-260
n1=$($PY - <<PYEOF
import sys; sys.path.insert(0, '$T'); import census
r = census.census('$SET/level.shr'); print(r['props_noop'] + r['sprops_noop'])
PYEOF
)
[ "$n1" -gt 0 ] || { echo "КРАСНОЕ: в данных L1 нет кусков с пустым смешиванием"; fail=1; }
$PY $T/mkref.py $SET/level.shr $W/ref/level.shr
echo "--- 2) орбита вокруг автомата L1"
cp $W/ref/level.shr $W/ovl/level.shr
$RUN $T/orbit.txt g907_old $OLD 400 >/dev/null; rm -rf $W/old; mv $W/out_g907_old $W/old
OVL=$W/ovl $RUN $T/orbit.txt g907_truth $OLD 400 >/dev/null; mv $W/out_g907_truth $W/truth
$RUN $T/orbit.txt g907_new $NEW 400 >/dev/null; mv $W/out_g907_new $W/new
$PY $T/compare.py $W/old $W/truth $W/new || fail=1
echo "--- 3) журнал движка"
got=$(grep -h '^BLENDOPQ level=1 ' $W/new/smoke.txt | head -1); echo "  $got"
pc=$(echo "$got" | sed -n 's/.*pieces=\([0-9]*\).*/\1/p'); [ -n "$pc" ] && [ "$pc" = "$n1" ] || { echo "КРАСНОЕ: BLENDOPQ pieces='$pc', перепись $n1"; fail=1; }
[ $fail = 0 ] && echo PASS || echo FAIL; exit $fail
