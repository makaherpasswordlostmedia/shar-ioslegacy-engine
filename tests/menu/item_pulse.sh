#!/bin/bash
# Гейт правки 412: пульс выбранного пункта главного меню по числам SLES_518.97 — безголовый эмулятор, ~1 мин.
#   tests/menu/item_pulse.sh [GREEN_EBOOT]   общий раннер tools/emu_run.sh (набор данных SET, по умолчанию тур TEST59); без аргумента зелёный собирается сам (набор тура со смоуком); красный — тот же набор + -DMENU_PULSE924_OLD=1
#   №889 (23.10) снял пульс главного меню, №924 (24.10) вернул: зелёная — обычная сборка; красные — -DMENU_PULSE924_OLD=1 (строка стоит, как до №924) и -DMENU_PULSE_OLD=1 (пульса нет нигде)
#   tests/menu889/check.py (строка стоит) теперь зелёный на сборке -DMENU_PULSE924_OLD=1
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; cd "$ROOT"
OUTD=${W:-$ROOT/build/gates/412}; rm -rf "$OUTD"; mkdir -p "$OUTD"; export OUT=$OUTD
G=${1:-}; [ -n "$G" ] || { tour_build build_t60 || exit 2; G=$ROOT/viewer/build_t60/EBOOT.PBP; }
tour_build build_t60_pulse924_old -DMENU_PULSE924_OLD=1 || { echo "FAIL: красная сборка"; exit 2; }; Rd=$ROOT/viewer/build_t60_pulse924_old/EBOOT.PBP
$RUN tests/menu/item_pulse.txt ip_green "$G" 120 > /dev/null & $RUN tests/menu/item_pulse.txt ip_red "$Rd" 120 > /dev/null & wait
"$PY" tests/menu/item_pulse.py "$OUTD/out_ip_green"; rg=$?
echo "красный (-DMENU_PULSE924_OLD=1, как HEAD до №924; строки MENUITEM в нём есть, падает по ширине/фазе):"; "$PY" tests/menu/item_pulse.py "$OUTD/out_ip_red" --expect-fail; rr=$?
[ $rg -eq 0 ] && [ $rr -eq 0 ] && { echo "ИТОГ: PASS (зелёный $OUTD/out_ip_green, красный пойман $OUTD/out_ip_red)"; exit 0; }
echo "ИТОГ: FAIL (зелёный rc=$rg, красный пойман=$([ $rr -eq 0 ] && echo да || echo НЕТ))"; exit 1
