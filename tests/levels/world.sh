#!/bin/bash
# Гейт «мир уровня вокруг города» (29.09, уровни 1–7): атмосфера, музыка езды, радар, фон паузы, газета загрузки, трафик.
# Каждая проверка — сначала КРАСНЫЙ на подложенном плохом входе, потом ЗЕЛЁНЫЙ на настоящих данных. Наборы уровней —
# build/levels/l<N>/ (у уровня 1 — build/ рядом с EBOOT, если там есть), load.shr — build/load.shr.
#   атмосфера   tests/levels/ambience_check.py: ворота уровня -> регионы ambience.rms (tools/rms.py); красный — пакет звука
#               уровня 3 с пустой привязкой (как было у 2–7 до 29.09)
#   музыка      tests/levels/music_check.py: езда = регион Sunday_Drive_region композиции; красные — регион переименован,
#               прежнее правило «строки между Level_Intro и Sunday_Drive_region» (уровень 5 играл вступление уровня 1)
#   интерфейс   tests/levels/hud_level_check.py: радар l<N>hudmap на дорогах уровня, фон паузы PauseBgd.pag ingamel<N>,
#               газета loading<N> кадром N-1; красные — карта уровня 1 на уровне 3, пакет уровня 1 на уровне 4 (затемнение
#               паузы), перекрашенный фон паузы, газеты 1 и 3 переставлены
#   трафик      tests/levels/traffic_level_check.py: машины и пешеходы TRF1 = leveli.mfk; красный — трафик уровня 1 на уровне 3
#   песочница   tools/sandbox/level_check.py --stages disk,shr,packs: красный — пакеты уровня 1 (интерфейс, трафик) на уровне 3
#   tests/levels/world.sh [уровни, по умолчанию 1..7]   -> PASS / FAIL, журнал build/gates/world_*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; G=build/gates; mkdir -p "$G" build/gates/world_tmp
LEVELS=${*:-1 2 3 4 5 6 7}
red=0; nred=0; green=0; ngreen=0
R() { nred=$((nred + 1)); local n="$1"; shift; if "$@" > "$G/world_red_$n.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: $n"; else red=$((red + 1)); echo "красный ($n): $(grep -m1 -E 'ПРОВАЛ|FAIL' "$G/world_red_$n.txt" | cut -c1-120)"; fi; }
Gn() { ngreen=$((ngreen + 1)); local n="$1"; shift; if "$@" > "$G/world_green_$n.txt" 2>&1; then green=$((green + 1)); echo "зелёный ($n): $(tail -1 "$G/world_green_$n.txt" | cut -c1-110)"; else echo "НЕ ЗЕЛЁНЫЙ: $n — $(grep -m1 -E 'ПРОВАЛ|FAIL' "$G/world_green_$n.txt" | cut -c1-120)"; fi; }
T=build/gates/world_tmp
l1() { [ -f "build/$1" ] && echo "build/$1" || echo "build/levels/l1/$1"; }

# атмосфера
R ambience_empty_l3 $PY tests/levels/ambience_check.py --level 3 --plant $T/amb_empty_l3
Gn ambience $PY tests/levels/ambience_check.py --level $LEVELS
# музыка езды
R music_region $PY tests/levels/music_check.py --plant
R music_strings $PY tests/levels/music_check.py --plant-strings
Gn music $PY tests/levels/music_check.py
# интерфейс уровня
R radar_l1_on_l3 $PY tests/levels/hud_level_check.py --level 3 --ui build/levels/l1/ui.shr
R pause_l1_on_l4 $PY tests/levels/hud_level_check.py --level 4 --ui build/levels/l1/ui.shr
R pause_color_l2 $PY tests/levels/hud_level_check.py --level 2 --plant-pause $T/pause_l2.shr
[ -f build/load.shr ] && R news_swap $PY tests/levels/hud_level_check.py --level 1 3 --plant-news $T/news_swap.shr
Gn hud $PY tests/levels/hud_level_check.py --level $LEVELS
# трафик
R traffic_l1_on_l3 $PY tests/levels/traffic_level_check.py --level 3 --traffic "$(l1 traffic.shr)"
Gn traffic $PY tests/levels/traffic_level_check.py --level $LEVELS
# песочница уровня
R sandbox_l3_foreign $PY tools/sandbox/level_check.py --level 3 --stages packs --ui build/levels/l1/ui.shr --traffic "$(l1 traffic.shr)"
for L in $LEVELS; do Gn "sandbox_l$L" $PY tools/sandbox/level_check.py --level $L --stages disk,shr,packs; done

echo "красных поймано $red из $nred, зелёных $green из $ngreen"
[ $red = $nred ] && [ $green = $ngreen ] && echo "PASS" || { echo "FAIL"; exit 1; }
