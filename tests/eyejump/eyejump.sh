#!/bin/bash
# №916б: гейт рывков глаза пешком (8 прогонов эмулятора параллельно): YARD — двор Симпсонов (CAMCROSS),
# PK_L1 — человек на линии перелёта глаза (flag camkick + flag pedbehind: место и время заданы сценарием), WK_L1 — автопилот ходьбы L1 (охрана), WK_L6 — ходьба L6 (допустим один рывок), FLIP_L1 — перескок камеры у стены на фасаде L1 по записи PS2 (красный камера как было), WK_L4 и WK_L7 — ходьба без рывков (Гомера ставим на улицу: уровень начинается в комнате дома).
# Новый код — зелёный, «как было» (flag camcrossold 1 / camsoftpplold 1 / camflip1old 1) — красный. Использование: eyejump.sh [EBOOT] ; нужен tools/smoke_headless.py (I=корень дерева) и набор данных run.sh
H=$(cd "$(dirname "$0")" && pwd); B=${1:-$H/../../viewer/build_x/EBOOT.PBP}; OUT=${OUT:-$H/out}; export OUT
for t in yard_y:yn yard_yo:yo pk_n:pn pk_o:po walk1_n:wn walk6_n:xn flip_n:fn flip_o:fo walk4_n:w4 walk7_n:w7 carw_n:cn carw_o:co; do bash ${RUN:-$H/../../tools/emu_run.sh} $H/${t%%:*}.txt g_${t##*:} $B 900 >/dev/null 2>&1 & done; wait
rc=0
chk() { python3 $H/eyejump.py $OUT/out_g_$1/smoke.txt --scene $2 ${@:3} || rc=1; }
red() { python3 $H/eyejump.py $OUT/out_g_$1/smoke.txt --scene $2 ${@:3} --expect fail >/dev/null; [ $? = 0 ] && echo "$2, прежний код: красный (ожидаемо)" || { echo "$2, прежний код НЕ красный"; rc=1; }; }
chk yn YARD; red yo YARD
chk pn PK_L1; red po PK_L1; chk wn WK_L1
chk xn WK_L6 --cuts 1   # красного у WK_L6 больше нет: на test67/test68 автопилот L6 не упирается в стену с перескоком (нет CAMFLIP), camflip1old ничего не меняет — красный перенесён на FLIP_L1
chk fn FLIP_L1 --lim 0.3; red fo FLIP_L1 --lim 0.3   # №916в: перескок у стены на фасаде L1 (z 180,9): новый код 0,19 м за кадр, прежний (flag camflip1old 1) 0,45 м
chk w4 WK_L4; chk w7 WK_L7   # красного у WK_L7 больше нет: автопилот L7 на test68 не ставит машину за спину (10,23 м и глаз в кузове были на другом маршруте) — красный №982 перенесён на CARW_L1
chk cn CARW_L1 --noflip; red co CARW_L1 --noflip   # №982: автобус трафика за спиной Гомера (flag trfspawn 2, Гомер лицом от него); прежнее (flag camcar982old 1): машина как стена — перескок камеры через героя (CAMFLIP 1), новое — ни одного
[ $rc = 0 ] && echo 'GATE PASS' || echo 'GATE FAIL'; exit $rc
