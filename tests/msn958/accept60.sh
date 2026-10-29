#!/bin/bash
# №958 приёмка: L6 не ставит цель «поехать в дом Гомера» (L1 M1). Пути на L6: NEW GAME на L6; пауза -> MISSION SELECT -> ◄ (L6 -> L5) -> ✕, затем ► (L5 -> L6) -> ✕ (настоящий интерфейс).
# Аргумент 1 — EBOOT тура (сборка по наряду TEST61). Проверка tests/msnhome/check.py levels. Красный контроль — те же флаги, что у №943 (flag mscursorold/lvdeferold/msnswitchold 1): обязан упасть.
H=$(cd "$(dirname "$0")" && pwd); W=$H/../..; E=${1:?EBOOT}; OUT=${OUT:-$H/out}; mkdir -p $OUT; export EMU_OWNER=${EMU_OWNER:-Управление} EMU_MINE=${EMU_MINE:-2} OUT; rc=0
awk '{print} /^flag menu/ && !d {print "flag mscursorold 1\nflag lvdeferold 1\nflag msnswitchold 1"; d=1}' $H/s6_hop.txt > $OUT/s6_hop_red.txt
bash $W/tools/emu_run.sh $H/s6_hop.txt n $E 700 >/dev/null 2>&1 & bash $W/tools/emu_run.sh $OUT/s6_hop_red.txt o $E 700 >/dev/null 2>&1 &
bash $W/tools/emu_run.sh $H/s6_new.txt nn $E 400 >/dev/null 2>&1 & wait
echo "== №958 зелёный: переходы L6->L5->L6"; python3 $W/tests/msnhome/check.py levels $OUT/out_n/smoke.txt || rc=1
echo "== №958 зелёный: NEW GAME на L6, цель не «домой»"; grep -q '^MSNHUD cur=m1 .*stagetext="TALK TO APU"' $OUT/out_nn/smoke.txt && echo "  ok  L6: TALK TO APU" || { echo "  FAIL L6 новая игра: нет TALK TO APU"; rc=1; }
grep -q 'SIMPSONS HOUSE' $OUT/out_nn/smoke.txt && { echo "  FAIL в L6 есть цель SIMPSONS HOUSE"; rc=1; }
echo "== №958 красный (прежние правила №943)"; python3 $W/tests/msnhome/check.py levels $OUT/out_o/smoke.txt && { echo "КРАСНЫЙ КОНТРОЛЬ НЕ КРАСНЫЙ"; rc=1; }
[ $rc = 0 ] && echo "PASS" || echo "FAIL"; exit $rc
