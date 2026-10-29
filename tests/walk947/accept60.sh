#!/bin/bash
# №947/№947б приёмка: пешком управление как до №916/№920 (стик относительно ТЕКУЩЕГО вида, разворот бегом назад бежит назад); курс держится, только когда ракурс меняет сама игра (перескок камеры у стены).
# Аргумент 1 — EBOOT тура (сборка по наряду TEST61, build_t60). Окружение: EMU_OWNER, OUT (по умолчанию tests/walk947/out), RUN (раннер, по умолчанию tools/emu_run.sh)
# Зелёный — новый код; красный — flag ctrl947old 1 (правило №916/№920: кадр держится, пока стик не отпущен): разворот бегом идёт вперёд, FAIL.
H=$(cd "$(dirname "$0")" && pwd); T=$H/..; E=${1:?EBOOT}; export OUT=${OUT:-$H/out}; RUN=${RUN:-$H/../../tools/emu_run.sh}; export EMU_OWNER=${EMU_OWNER:-Управление} EMU_MINE=${EMU_MINE:-2}; rc=0; mkdir -p $OUT
red() { awk '{print} /^flag camlog/ && !d {print "flag ctrl947old 1"; d=1}' "$1" > "$2"; }
red $H/walk947.txt $OUT/walk947_red.txt
bash $RUN $H/walk947.txt n $E 400 >/dev/null 2>&1 & bash $RUN $OUT/walk947_red.txt o $E 400 >/dev/null 2>&1 &
wait
echo "== №947 зелёный (новый код)"; python3 $H/walk947.py $OUT/out_n/smoke.txt || rc=1
echo "== №947 красный (flag ctrl947old 1)"; python3 $H/walk947.py $OUT/out_o/smoke.txt --expect fail || { echo "КРАСНЫЙ КОНТРОЛЬ НЕ КРАСНЫЙ"; rc=1; }
[ $rc = 0 ] && echo "PASS" || echo "FAIL"; exit $rc
