#!/bin/bash
# №916б: гейт рывков глаза пешком (8 прогонов эмулятора параллельно): YARD — двор Симпсонов (CAMCROSS),
# PK_L1 — человек на линии перелёта глаза (flag camkick + flag pedbehind: место и время заданы сценарием), WK_L1 — автопилот ходьбы L1 (охрана), WK_L6 — перескок камеры у стены по записи PS2 (один рывок, не два), WK_L4 и WK_L7 — ходьба без рывков (Гомера ставим на улицу: уровень начинается в комнате дома).
# Новый код — зелёный, «как было» (flag camcrossold 1 / camsoftpplold 1 / camflip1old 1) — красный. Использование: eyejump.sh [EBOOT] ; нужен tools/smoke_headless.py (I=корень дерева) и набор данных run.sh
H=$(cd "$(dirname "$0")" && pwd); B=${1:-$H/../../viewer/build_x/EBOOT.PBP}; OUT=${OUT:-$H/out}; export OUT
for t in yard_y:yn yard_yo:yo pk_n:pn pk_o:po walk1_n:wn walk6_n:xn walk6_fo:xo walk4_n:w4 walk7_n:w7; do bash ${RUN:-$H/../../tools/emu_run.sh} $H/${t%%:*}.txt g_${t##*:} $B 900 >/dev/null 2>&1 & done; wait
rc=0
chk() { python3 $H/eyejump.py $OUT/out_g_$1/smoke.txt --scene $2 ${@:3} || rc=1; }
red() { python3 $H/eyejump.py $OUT/out_g_$1/smoke.txt --scene $2 ${@:3} --expect fail >/dev/null; [ $? = 0 ] && echo "$2, прежний код: красный (ожидаемо)" || { echo "$2, прежний код НЕ красный"; rc=1; }; }
chk yn YARD; red yo YARD
chk pn PK_L1; red po PK_L1; chk wn WK_L1
chk xn WK_L6 --cuts 1; red xo WK_L6 --cuts 1
chk w4 WK_L4; chk w7 WK_L7
[ $rc = 0 ] && echo 'GATE PASS' || echo 'GATE FAIL'; exit $rc
