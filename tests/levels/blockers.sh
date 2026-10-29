#!/bin/bash
# Гейт «блокеры экспорта уровней 2–7» (docs/РЕЦЕПТ_УРОВНЯ.md §3.1/§6.3, 29.09): каждый блокер — сначала КРАСНЫЙ на подложенном
# плохом входе, потом ЗЕЛЁНЫЙ на настоящих данных. Уровни — в build/levels/l<N>/ (сборка по рецепту §4, --level N).
#   1 слоты стейтпропов > 32   tests/levels/slots_check.py + slots_host.c (viewer/stateprops.c): маска в 32 бита — провал
#   2 рельс камеры > 9 точек   tests/rooms/cams_check.py --level 3/6 + cams_host.c (viewer/roomcam.c): рельс обрезан до 9 — провал
#   3 AddBehaviour с текстом   tests/levels/behaviour_check.py: прежний разбор / текст в поведении осы — провал
#   4 старт, машина, небо      tests/levels/start_check.py: старт в центре габарита, машина чужого уровня, неба нет — провал
#     музыка уровня            tests/levels/music_check.py: регион езды переименован — провал; уровень 1 = прежняя таблица
#   tests/levels/blockers.sh [уровни, по умолчанию 1..7 — какие собраны]   -> PASS / FAIL, журнал build/gates/blockers.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; G=build/gates; mkdir -p "$G"
LEVELS=${*:-1 2 3 4 5 6 7}
red=0; nred=0; green=0; ngreen=0
R() { nred=$((nred + 1)); local n="$1"; shift; if "$@" > "$G/red_$n.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН: $n"; else red=$((red + 1)); echo "красный ($n): $(grep -m1 -E 'ПРОВАЛ|FAIL|spInit|красный' "$G/red_$n.txt" | cut -c1-110)"; fi; }
Gn() { ngreen=$((ngreen + 1)); local n="$1"; shift; if "$@" > "$G/green_$n.txt" 2>&1; then green=$((green + 1)); echo "зелёный ($n): $(tail -1 "$G/green_$n.txt" | cut -c1-110)"; else echo "НЕ ЗЕЛЁНЫЙ: $n — $(grep -m1 -E 'ПРОВАЛ|FAIL' "$G/green_$n.txt" | cut -c1-110)"; fi; }
lvl() { [ -f "build/levels/l$1/$2" ] && echo "build/levels/l$1/$2" || { [ "$1" = 1 ] && [ -f "build/$2" ] && echo "build/$2"; }; }

# 1 слоты
cc -std=c11 -O2 -Wall -Wno-unused-function -I viewer tests/levels/slots_host.c viewer/stateprops.c viewer/col.c viewer/props.c viewer/coins.c viewer/car.c -lm -o $G/slots_host || exit 1
[ -f $G/slots.bin ] && [ tools/prp2_export.py -ot $G/slots.bin ] || $PY tests/levels/slots_check.py --make $G/slots.bin > $G/slots_make.txt 2>&1 || { echo "FAIL: экспорт слотов"; exit 1; }
$PY tests/levels/slots_check.py --truncate $G/slots.bin $G/slots_planted.bin
chk_slots() { $G/slots_host "$1" > "$1.host.txt" || return 1; $PY tests/levels/slots_check.py "$1.host.txt" "${1%.bin}.json"; }
R slots_32 chk_slots $G/slots_planted.bin
Gn slots chk_slots $G/slots.bin
for L in $LEVELS; do for f in level.shr collect-l$L.shr; do p=$(lvl $L $f); [ -n "$p" ] && Gn "spr1_l${L}_${f%%.*}" $G/slots_host --pack "$p"; done; done

# 2 рельсы (комнаты уровней 3 и 6: Обсерватория, 13 точек); уровень 1 — прежний зелёный
cc -std=c99 -O2 -Wall -I viewer tests/rooms/cams_host.c viewer/roomcam.c -lm -o $G/cams_host || exit 1
chk_cams() { $G/cams_host "$1" > "$1.host.txt" || return 1; $PY tests/rooms/cams_check.py "$1.host.txt" --level "$2"; }
for L in $LEVELS; do
  p=$(lvl $L interiors-l$L-gfx.bin); [ -n "$p" ] || continue
  if $PY tests/rooms/cams_check.py --plant-rail9 "$p" $G/rail9_l$L.bin > /dev/null 2>&1; then R "rail9_l$L" chk_cams $G/rail9_l$L.bin $L; fi
  Gn "cams_l$L" chk_cams "$p" $L
done

# 3 AddBehaviour
R behaviour $PY tests/levels/behaviour_check.py --plant
Gn behaviour $PY tests/levels/behaviour_check.py

# 4 старт / машина / небо; музыка
for L in $LEVELS; do
  p=$(lvl $L level.shr); [ -n "$p" ] || continue
  $PY tests/levels/start_check.py --plant-center "$p" $G/center_l$L.shr; R "start_center_l$L" $PY tests/levels/start_check.py --level $L $G/center_l$L.shr
  $PY tests/levels/start_check.py --plant-nosky "$p" $G/nosky_l$L.shr; R "nosky_l$L" $PY tests/levels/start_check.py --level $L $G/nosky_l$L.shr
  Gn "start_l$L" $PY tests/levels/start_check.py --level $L "$p"
done
p1=$(lvl 1 level.shr); [ -n "$p1" ] && R car_of_l1_as_l4 $PY tests/levels/start_check.py --level 4 "$p1"
R music $PY tests/levels/music_check.py --plant
Gn music $PY tests/levels/music_check.py

echo "красных поймано $red из $nred, зелёных $green из $ngreen"
[ $red = $nred ] && [ $green = $ngreen ] && echo "PASS" || { echo "FAIL"; exit 1; }
