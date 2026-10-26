#!/bin/bash
# №991 приёмка: контур машин NPC не закрывает крышу тушью в три четверти сверху и с торца.   EB=<EBOOT тура> [SET=<набор>] [OUT=<папка>] tests/carink991/accept.sh      (последняя строка: PASS или FAIL)
#   зелёный: на пяти ракурсах (8–26 м) прежнее и новое с одного места одним EBOOT (flag carink991 0/1): новое освобождает от туши не меньше 150 пикселей, контур остаётся
#   красный: тот же сценарий, но «новое» тоже 0 — гейт обязан упасть
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
I=$(cd "$(dirname "$0")/../.." && pwd); cd "$I"; PY="$I/.venv/bin/python3"; [ -x "$PY" ] || PY=python3
EB=${EB:?нужен EB=<EBOOT тура>}; export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test70tour/PSP/GAME/SHARTEST15}; export OUT=${OUT:-/tmp/ci991_accept} EMU_OWNER=${EMU_OWNER:-Оптимизация} EMU_MINE=${EMU_MINE:-2}
mkdir -p "$OUT"; BAD=0; ok() { echo "  [ok]  $1"; }; bad() { echo "  [BAD] $1"; BAD=$((BAD + 1)); }
$PY tests/carink991/gen_scenario.py green > "$OUT/s_green.txt"; $PY tests/carink991/gen_scenario.py red > "$OUT/s_red.txt"
tools/emu_run.sh "$OUT/s_green.txt" ci_green "$EB" 400 > "$OUT/ci_green.log" 2>&1 &
tools/emu_run.sh "$OUT/s_red.txt" ci_red "$EB" 400 > "$OUT/ci_red.log" 2>&1 &
wait
echo "-- зелёный: новое против прежнего"
$PY tests/carink991/check.py "$OUT/out_ci_green" && ok "крыша и бока свободны от туши, контур остался" || bad "новое не освободило крышу"
echo "-- красный контроль: «новое» = прежнее"
$PY tests/carink991/check.py "$OUT/out_ci_red" > "$OUT/red.txt" 2>&1 && bad "красный контроль прошёл (гейт ничего не ловит)" || ok "красный контроль упал, как должен ($(tail -1 "$OUT/red.txt"))"
[ $BAD = 0 ] && echo PASS || echo FAIL
