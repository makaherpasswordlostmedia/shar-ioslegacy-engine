#!/bin/bash
# №907-город гейт: куски ГОРОДА с флагом 2 при пустом смешивании (непрозрачные текстура и вершины) — непрозрачными, кроме «листов» моря (№863).
# Использование: city_gate.sh NEW_EBOOT OLD_EBOOT   (RUN, SET, PY — как у gate.sh; подмена level.shr — папкой-наложением OVL)
#  1) счёт: журнал движка OPQ863 pieces_unblend/tris_unblend == правило по файлу (city.plan) на L1, L3, L6
#  2) картинки L1 (city_l1.txt): OLD на данных диска, TRUTH = OLD на данных со снятым в файле флагом (mkref_city.py), NEW на данных диска
# Красный контроль: city_gate.sh OLD_EBOOT OLD_EBOOT -> FAIL (нет pieces_unblend, картинка как у OLD)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/inside907
NEW=$1; OLD=$2; W=${W:-$ROOT/build/gates/cgate907}; export OUT=$W; rm -rf $W; mkdir -p $W/ref $W/ovl; fail=0
echo "--- 1) счёт по данным и журналу движка"
for L in 1 3 6; do f=$SET/level.shr; [ $L -gt 1 ] && f=$SET/l$L/level.shr
  want=$($PY $T/mkref_city.py $f $W/ref/l$L.shr | sed -n 's/снят флаг 2 у \([0-9]*\) кусков города (\([0-9]*\) треугольников).*/\1 \2/p')
  if [ $L = 1 ]; then continue; fi
  printf 'flag level %s\nwait 14\nend\n' $L > $W/cnt$L.txt; $RUN $W/cnt$L.txt cg_l$L $NEW 240 >/dev/null
  got=$(grep -h '^OPQ863 level='$L' ' $W/out_cg_l$L/smoke.txt | sed -n 's/.*pieces_unblend=\([0-9]*\) tris_unblend=\([0-9]*\).*/\1 \2/p'); rm -rf $W/out_cg_l$L
  echo "  L$L: по файлу '$want', в журнале движка '$got'"; [ -n "$got" ] && [ "$got" = "$want" ] || { echo "КРАСНОЕ: L$L счёт не сошёлся"; fail=1; }
done
echo "--- 2) картинки L1"
$RUN $T/city_l1.txt cg_old $OLD 500 >/dev/null; mv $W/out_cg_old $W/old
cp $W/ref/l1.shr $W/ovl/level.shr; OVL=$W/ovl $RUN $T/city_l1.txt cg_truth $OLD 500 >/dev/null; mv $W/out_cg_truth $W/truth
$RUN $T/city_l1.txt cg_new $NEW 500 >/dev/null; mv $W/out_cg_new $W/new
$PY $T/city_compare.py $W/old $W/truth $W/new || fail=1
got=$(grep -h '^OPQ863 level=1 ' $W/new/smoke.txt | sed -n 's/.*pieces_unblend=\([0-9]*\) tris_unblend=\([0-9]*\).*/\1 \2/p'); want=$($PY $T/mkref_city.py $SET/level.shr $W/ref/x.shr | sed -n 's/снят флаг 2 у \([0-9]*\) кусков города (\([0-9]*\) треугольников).*/\1 \2/p')
echo "  L1: по файлу '$want', в журнале движка '$got'"; [ -n "$got" ] && [ "$got" = "$want" ] || { echo "КРАСНОЕ: L1 счёт не сошёлся"; fail=1; }
[ $fail = 0 ] && echo PASS || echo FAIL; exit $fail
