#!/bin/bash
# №914 гейт: flag drive в 5 сценах тура ездит весь срок и на машине уровня. Зелёный — новый код, красные — flag adclockold 1 / adseatold 1 / оба (прежнее поведение)
# Сцены езды (flag drive) и ходьбы (flag walk, walk914.txt). Аргумент 1 — EBOOT (сборка по строке из наряда), остальное — переменные раннера drive914_run.sh (SET, BINS, HZ, I)
H=$(cd "$(dirname "$0")" && pwd); E=${1:?EBOOT}; export OUT=${OUT:-$H/out}; rc=0
for v in new:drive914 clock:drive914_oldclock seat:drive914_oldseat old:drive914_old wnew:walk914 wclock:walk914_oldclock; do n=${v%%:*}; f=${v##*:}
  bash $H/drive914_run.sh $H/$f.txt $n $E 2400 >/dev/null 2>&1 &
done; wait
echo "== зелёный (новый код)"; python3 $H/drive914.py $OUT/out_new/smoke.txt || rc=1
for n in clock seat old; do echo "== красный: $n"; python3 $H/drive914.py $OUT/out_$n/smoke.txt --expect fail || { echo "КРАСНЫЙ КОНТРОЛЬ $n НЕ КРАСНЫЙ"; rc=1; }; done
echo "== walk, зелёный (новый код)"; python3 $H/drive914.py $OUT/out_wnew/smoke.txt --walk --min 20 || rc=1
echo "== walk, красный: часы"; python3 $H/drive914.py $OUT/out_wclock/smoke.txt --walk --min 20 --expect fail || { echo "КРАСНЫЙ КОНТРОЛЬ wclock НЕ КРАСНЫЙ"; rc=1; }
exit $rc
