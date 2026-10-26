#!/bin/bash
# ПРИЁМКА №995 (окно «Небо», ветка t71/beam995): свет под тарелкой L7 — один полупрозрачный конус от днища до земли вместо билбордов луча и блинка; в игре «flag beam995 0» / файл beam995old / BEAM995_OLD=1 — как в TEST70.
#   1 сборка   EBOOT тура
#   2 движок   ufo.txt (миссия m3 L7, четыре вида; каждый сначала beam995 0, потом 1) и красный: тот же сценарий, где все «flag beam995 1» заменены на 0 (конус не включается)
#   3 проверка check.py: конус рисуется только в on=1, 56 треугольников; кадры side различаются полосой под тарелкой; красный обязан упасть; лист «TEST70 / стало»
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; H=$ROOT/tests/beam995
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
PY=$ROOT/.venv/bin/python; SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test70tour/PSP/GAME/SHARTEST15}
A=${ACC_OUT:-$ROOT/build/b995/accept}; rm -rf "$A"; mkdir -p "$A"; export EMU_OWNER=${EMU_OWNER:-Небо} OUT=$A EMU_MINE=${EMU_MINE:-2} SET
FAIL=0; say() { echo "[$(date +%H:%M:%S)] $*"; }
res() { if [ "$1" = 0 ]; then say "  ok   $2"; else say "  ПАДАЕТ $2"; FAIL=1; fi; }
red() { if [ "$1" != 0 ]; then say "  ok   красное: $2"; else say "  ПАДАЕТ красное не упало: $2"; FAIL=1; fi; }
( cd $H && $PY -I gen.py ); sed 's/^flag beam995 1$/flag beam995 0/' $H/ufo.txt > $A/ufo_red.txt
say "1 сборка"; bash $H/mk.sh new "" > /dev/null; res $? "EBOOT тура"; EN=$ROOT/viewer/build_bm_new/EBOOT.PBP
say "2 движок: новый и красный (около 3 минут)"
( bash $ROOT/tools/emu_run.sh $H/ufo.txt new "$EN" 400 > $A/emu_new.log 2>&1 ) & ( bash $ROOT/tools/emu_run.sh $A/ufo_red.txt red "$EN" 400 > $A/emu_red.log 2>&1 ) & wait
for v in new red; do [ -s "$A/out_$v/smoke.txt" ] && grep -q "^END" "$A/out_$v/smoke.txt"; res $? "прогон $v дошёл до END"; done
say "3 проверка"
$PY -I $H/check.py $A/out_new | tee $A/check_new.txt; [ "$(tail -1 $A/check_new.txt)" = PASS ]; res $? "конус рисуется, полоса под тарелкой на снимке"
$PY -I $H/check.py $A/out_red > $A/check_red.txt; [ "$(tail -1 $A/check_red.txt)" = PASS ]; red $? "флаг не включается — проверка падает"
$PY -I $H/sheet.py $A/out_new $A/sheet_TEST70_stalo.png
[ $FAIL = 0 ] && echo PASS || echo FAIL
