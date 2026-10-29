#!/bin/bash
# ПРИЁМКА №990 (окно «Небо», ветка t71/pool990): эллипсов света на полу под фонарями нет ни у ламп таблицы света, ни у конусов клеток/стейтпропов; конусы с затуханием вниз на месте. Одна команда: tests/pool990/accept60.sh, последняя строка PASS или FAIL
#   1 сборка   EBOOT тура (новое) и красный EBOOT (-DPOOL990_OLD=1: эллипсы как в TEST70)
#   2 движок   stills.txt на новом (места L1, L3, L4, L5 улица и мост, L6 причал, L7 ночь: pool990 0, затем 1 с той же камерой) и defaults.txt (езда по всем семи уровням без единой строки flag pool990) на новом и на красном
#   3 проверка check.py: в парах эллипсов у нового 0, у прежнего есть, конусов столько же; по умолчанию в езде эллипсов нет нигде; красный EBOOT в езде обязан упасть; листы кадров
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; H=$ROOT/tests/pool990
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
PY=$ROOT/.venv/bin/python; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test70tour/PSP/GAME/SHARTEST15}
A=${ACC_OUT:-$ROOT/build/p990/accept}; rm -rf "$A"; mkdir -p "$A"; export EMU_OWNER=${EMU_OWNER:-Небо} OUT=$A EMU_MINE=${EMU_MINE:-2} SET
FAIL=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
res() { if [ "$1" = 0 ]; then say "  ok   $2"; else say "  ПАДАЕТ $2"; FAIL=1; fi; }
red() { if [ "$1" != 0 ]; then say "  ok   красное: $2"; else say "  ПАДАЕТ красное не упало: $2"; FAIL=1; fi; }
( cd $H && $PY -I gen.py )
say "1 сборка"; bash $H/mk.sh new "" > /dev/null; res $? "EBOOT тура"; bash $H/mk.sh oldc "-DPOOL990_OLD=1" > /dev/null; res $? "EBOOT красный (POOL990_OLD=1)"
EN=$ROOT/viewer/build_pl_new/EBOOT.PBP; EO=$ROOT/viewer/build_pl_oldc/EBOOT.PBP
say "2 движок: места и езда на новом, езда на красном (около 10 минут)"
( bash $ROOT/tools/emu_run.sh $H/stills.txt st "$EN" 1200 > $A/emu_st.log 2>&1 ) & ( bash $ROOT/tools/emu_run.sh $H/defaults.txt dfo "$EO" 1200 > $A/emu_dfo.log 2>&1 ) & wait
bash $ROOT/tools/emu_run.sh $H/defaults.txt dfn "$EN" 1200 > $A/emu_dfn.log 2>&1
for v in st dfn dfo; do [ -s "$A/out_$v/smoke.txt" ] && grep -q "^END" "$A/out_$v/smoke.txt"; res $? "прогон $v дошёл до END"; done
say "3 проверка"
$PY -I $H/check.py $A/out_st/smoke.txt | tee $A/check_st.txt; [ "$(tail -1 $A/check_st.txt)" = PASS ]; res $? "места: эллипсов нет, конусы на месте"
$PY -I $H/check.py $A/out_dfn/smoke.txt --default | tee $A/check_dfn.txt | tail -4; [ "$(tail -1 $A/check_dfn.txt)" = PASS ]; res $? "езда по семи уровням: эллипсов нет нигде"
$PY -I $H/check.py $A/out_dfo/smoke.txt --default > $A/check_dfo.txt; [ "$(tail -1 $A/check_dfo.txt)" = PASS ]; red $? "красный EBOOT (эллипсы как в TEST70) в езде падает"
$PY -I $H/check.py $A/out_st/smoke.txt --default > $A/check_red2.txt; [ "$(tail -1 $A/check_red2.txt)" = PASS ]; red $? "пары (on=0 прежнее) под правило «по умолчанию» падают"
$PY -I $H/sheet.py $A/out_st $A/sheet_TEST70_stalo.png | tee $A/sheet.txt
[ $FAIL = 0 ] && echo PASS || echo FAIL
