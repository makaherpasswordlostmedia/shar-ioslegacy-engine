#!/bin/bash
# №971/№972 приёмка: боковые файлы заливки машин NPC (tools/car_flat.py) свежие и низ машины тёмный.   EB=<EBOOT тура> [SET=<набор>] [OUT=<папка>] tests/carfill971/accept60.sh      (последняя строка: PASS или FAIL)
#   1) данные: набор совпадает с выходом генератора на текущем коде (tools/check_sidecars.py, 14 файлов); красный: файлы, собранные с CARFLAT_DARK972_OLD=1 (до правки), обязаны не совпасть
#   2) картинка: дальняя версия минивэна L1 сзади снизу (колёса и днище), прежние и новые данные в одном EBOOT: под кузовом нет цвета кузова и много тёмного; красный: прежние данные обязаны упасть
#   3) машины миссий: у новых данных почти чёрных вершин в 1,3 раза больше, чем у прежних
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
I=$(cd "$(dirname "$0")/../.." && pwd); cd "$I"; PY="$I/.venv/bin/python3"; [ -x "$PY" ] || PY=python3
EB=${EB:?нужен EB=<EBOOT тура>}; export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test66tour/PSP/GAME/SHARTEST15}; export OUT=${OUT:-/tmp/cf971_accept} EMU_OWNER=${EMU_OWNER:-Оптимизация} EMU_MINE=${EMU_MINE:-2}
mkdir -p "$OUT"; BAD=0; ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
gen() {   # gen ПАПКА [1 — как до №972]
  rm -rf "$1"; mkdir -p "$1"
  for n in 1 2 3 4 5 6 7; do ( if [ $n = 1 ]; then d=$SET; o=$1; else d=$SET/l$n; o=$1/l$n; mkdir -p $o; fi; [ "${2:-0}" = 1 ] && export CARFLAT_DARK972_OLD=1
    $PY tools/car_flat.py $d/traffic.shr --sidecar $o/carflat930.bin >/dev/null 2>&1; $PY tools/car_flat.py $d/msncars-l$n.shr --sidecar $o/carflatm930.bin >/dev/null 2>&1 ) & done; wait; }
gen "$OUT/data_new" 0; gen "$OUT/data_old" 1
echo "-- 1) данные набора против генератора"
$PY tools/check_sidecars.py "$SET" "$OUT/data_new" > "$OUT/chk_new.txt" 2>&1 && ok "свежие файлы совпали с генератором (14 из 14)" || bad "свежие файлы не совпали: $(tail -1 "$OUT/chk_new.txt")"
$PY tools/check_sidecars.py "$SET" "$OUT/data_old" > "$OUT/chk_old.txt" 2>&1 && bad "красный контроль: файлы до №972 прошли проверку" || ok "красный контроль (файлы до №972) не совпали, как должны ($(tail -1 "$OUT/chk_old.txt"))"
echo "-- 2) картинка: низ дальней версии машины"
OVL="$OUT/data_new" tools/emu_run.sh tests/carfill971/scenario_lod.txt cf_new "$EB" 400 > "$OUT/cf_new.log" 2>&1 &
OVL="$OUT/data_old" tools/emu_run.sh tests/carfill971/scenario_lod.txt cf_old "$EB" 400 > "$OUT/cf_old.log" 2>&1 &
wait
$PY tests/carfill971/check.py img "$OUT/out_cf_new/m00_r.png" && ok "новые данные: низ тёмный" || bad "новые данные: под кузовом цвет или мало тёмного"
$PY tests/carfill971/check.py img "$OUT/out_cf_old/m00_r.png" > /dev/null && bad "красный контроль: прежние данные прошли" || ok "красный контроль (прежние данные) упал, как должен"
echo "-- 3) машины миссий"
$PY tests/carfill971/check.py data "$OUT/data_new/l3/carflatm930.bin" "$OUT/data_old/l3/carflatm930.bin" && ok "у машин миссий низ тёмный" || bad "у машин миссий почти чёрных вершин не прибавилось"
[ $BAD = 0 ] && echo PASS || echo FAIL
