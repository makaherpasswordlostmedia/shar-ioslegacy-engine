#!/bin/bash
# №947б: гейты управления пешком (бывш. №916/№920). Аргумент 1 — EBOOT тура (сборка по наряду TEST61). Раннер — tools/emu_run.sh (EMU_OWNER, OUT).
#  ctrl916 (CT_hold/CT_fresh): стик относительно ТЕКУЩЕГО вида; красный — flag ctrl947old 1 (правило №916/№920: кадр держится, пока стик не отпущен).
#  ctrl920 (TW_down/WJ_cont/WJ_drop): курс держится при непрерывном стике и при перескоке камеры у стены (камера игры); красный — flag flipbusyold 1.
# Разворот бегом назад — tests/walk947 (W_twice). Последняя строка GATE PASS / GATE FAIL
H=$(cd "$(dirname "$0")" && pwd); W=$H/../..; E=${1:?EBOOT}; export OUT=${OUT:-$H/out} EMU_OWNER=${EMU_OWNER:-Управление} EMU_MINE=${EMU_MINE:-2}; rc=0; mkdir -p $OUT
red() { awk -v f="$3" '{print} /^flag camlog/ && !d {print f; d=1}' "$1" > "$2"; }
red $H/ctrl916.txt $OUT/ctrl916_red.txt "flag ctrl947old 1"; red $H/ctrl920.txt $OUT/ctrl920_red.txt "flag flipbusyold 1"
bash $W/tools/emu_run.sh $H/ctrl916.txt n $E 900 >/dev/null 2>&1 & bash $W/tools/emu_run.sh $OUT/ctrl916_red.txt o $E 900 >/dev/null 2>&1 &
bash $W/tools/emu_run.sh $H/ctrl920.txt n20 $E 900 >/dev/null 2>&1 & bash $W/tools/emu_run.sh $OUT/ctrl920_red.txt o20 $E 900 >/dev/null 2>&1 & wait
echo "== №947б зелёный: стик от текущего вида"; python3 $H/ctrl916.py $OUT/out_n/smoke.txt || rc=1
echo "== №947б красный (flag ctrl947old 1)"; python3 $H/ctrl916.py $OUT/out_o/smoke.txt --expect fail || { echo "КРАСНЫЙ КОНТРОЛЬ НЕ КРАСНЫЙ"; rc=1; }
echo "== №947б зелёный: курс держится при перескоке камеры игрой"; python3 $H/ctrl920.py $OUT/out_n20/smoke.txt || rc=1
echo "== №947б красный (flag flipbusyold 1)"; python3 $H/ctrl920.py $OUT/out_o20/smoke.txt --expect fail || { echo "КРАСНЫЙ КОНТРОЛЬ НЕ КРАСНЫЙ"; rc=1; }
[ $rc = 0 ] && echo "GATE PASS" || echo "GATE FAIL"; exit $rc
