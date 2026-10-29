#!/bin/bash
# Гейт правки Роба 326 (04.10: «гонка со Скиннером всё равно не считает, кто первый: ехал рядом — не понимает в реальном времени»;
# указание Роба: «кто ближе к точке — тот и первый»; прежде правки 300, 178). Место игрока каждый кадр по точкам гонки ИГРОКА для
# всех (viewer/msncar.c mcRacePlaceRob): больше пройдено точек — впереди, поровну — кто ближе по прямой к той же следующей точке,
# гистерезис 1 м. Красный — нынешняя до 326 мера правки 300 (остаток метров, у соперника по его точкам): -DRACEPOS_300=1 /
# «flag racepos300 1».
# 1) Мак: tests/aicar/racepos_host.c — те же функции движка, точки с диска (m1, sr2, m7): рядом, на крюке, обгон, дрожание, срезка.
# 2) Безголовый эмулятор (~/.claude/skills/shar-level-polish/scripts/scen.py, EBOOT=viewer/build/EBOOT.PBP): S-M-R-T с чекпоинта,
#    старт гонки у триггера m1_skinner_start; start — игрок стоит на старте (Скиннер ближе к школе: 2-й); hook — игрок во встречной
#    полосе дороги Скиннера к m1_AI_path1 (его крюк на запад: x 42 против x 36), Скиннер проезжает рядом; side — игрок во встречной
#    дороге r2RoadNode (x 258) у его дороги на север r2RoadNode1 (x 245), Скиннер проезжает рядом; chase — автопилот игрока
#    быстрее следом; cut — перенос к школе (1-й) и back — назад к старту (2-й). Проверка racepos_check.py: каждая смена места (строка RACEPOS, пишется в кадр смены) — у равного расстояния
#    (≤ 1,5 м) или первым кадром после переноса; места на снимках не противоречат расстояниям; есть смена рядом в hook/side.
#    Правка 347: Скиннер больше не стоит 7–25 с в подпорной стене K11-4 (путь против хода среза 13), а едет улицей K11-3 и
#    финиширует на ~70 с прогона — chase 4 с вместо 10, перенос cut ближе к школе (100, 590: 96 м до финиша против 131), чтобы cut и
#    back снимались, пока Скиннер ещё в гонке и дальше игрока на cut (на 25 м и больше). Третий прогон «flag ledgeold 1» (прежний путь
#    через стену) — тот же сценарий обязан быть зелёным: место считается по правилу Роба при любом пути Скиннера.
#   tests/aicar/racepos.sh            оба этапа;   tests/aicar/racepos.sh --host   только Мак
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
export SCEN_ROOT="${SCEN_ROOT:-$ROOT}"
export TWINS_ROOT="${TWINS_ROOT:-$SCEN_ROOT}"
OUT=build/gates/racepos; mkdir -p "$OUT"; PY=.venv/bin/python; SCEN=~/.claude/skills/shar-level-polish/scripts/scen.py
EB="${EBOOT:-$ROOT/viewer/build/EBOOT.PBP}"; V=viewer; red=0; green=0; TAG="${RACEPOS_TAG:-racepos}"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V"
SRC="tests/aicar/racepos_host.c $V/msncar.c $V/car.c $V/col.c $V/traffic.c $V/homer.c $V/skin.c"
$CC -DRACEPOS_300=1 $SRC -lm -o "$OUT/host_red" 2> "$OUT/build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/build.txt"; exit 1; }
$CC $SRC -lm -o "$OUT/host" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
echo "Мак, красный (мера правки 300):"; "$OUT/host_red" | tee "$OUT/host_red.txt" | grep -E "FAIL|RESULT" | sed 's/^/  /'
if [ "${PIPESTATUS[0]}" != 0 ]; then echo "  упал, как должен"; red=$((red + 1)); else echo "  КРАСНЫЙ НЕ ПОЙМАН"; fi
echo "Мак, зелёный (правило Роба 326):"; "$OUT/host" | tee "$OUT/host.txt" | sed 's/^/  /'; [ "${PIPESTATUS[0]}" = 0 ] && green=$((green + 1))
if [ "${1:-}" = --host ]; then [ $red = 1 ] && [ $green = 1 ] && { echo PASS; exit 0; }; echo FAIL; exit 1; fi
mk() {   # $1 — служебный флаг или пусто
  printf '%s\n' 'scene spawn' 'wait 3' 'scene start' 'flag msn' 'wait 3' ${1:+"$1"} 'flag msnmain 1' 'wait 3' 'press cross' 'wait 3' \
    'flag msngo' 'wait 4' 'foot 216.6 169.8 -2.84' 'wait 2' 'press triangle' 'wait 4' \
    'scene start' 'goto 161 135 0' 'wait 1' 'shot rq_s0' 'wait 2' 'shot rq_s1' 'wait 2' 'shot rq_s2' \
    'scene hook' 'goto 42 216 0' 'wait 1' 'shot rq_k0'
  for i in 1 2 3 4 5 6 7 8 9 10; do printf '%s\n' 'wait 1' "shot rq_k$i"; done   # Скиннер едет к m1_AI_path1 (x 36) мимо игрока (x 42)
  printf '%s\n' 'scene side' 'goto 258 430 0' 'wait 1' 'shot rq_e0'
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do printf '%s\n' 'wait 1' "shot rq_e$i"; done   # мимо по r2RoadNode1 (x 245)
  printf '%s\n' 'scene chase' 'flag wpv 24' 'flag wp 252 452' 'flag wp 230 468' 'flag wp 209 486' 'flag wp 207 533' 'flag wp 190 560' \
    'flag wp 150 575' 'flag wp 100 590' 'flag wpgo'
  for i in 1 2 3 4; do printf '%s\n' 'wait 1' "shot rq_c$i"; done  # автопилот быстрее следом (правка 347: 4 с — Скиннер финиширует к ~70 с)
  printf '%s\n' 'scene cut' 'flag stop' 'goto 100 590 0' 'wait 1' 'shot rq_u0' 'wait 1' 'shot rq_u1' \
    'scene back' 'goto 160 137 0' 'wait 1' 'shot rq_b0' 'wait 1' 'shot rq_b1' 'end'
}
run() { mk "${2:-}" > "$OUT/$1.txt"; SCEN_EBOOT="$EB" SCEN_HOME="$ROOT/$OUT/home_$1" "$PY" "$SCEN" "${TAG}_$1" "$OUT/$1.txt" > "$OUT/$1_run.txt" 2>&1; }
run old 'flag racepos300 1' & run new & run ledge 'flag ledgeold 1' & wait
F="$TWINS_ROOT/build/twins/scen/full"   # scen.py пишет туда (common.DATA)
echo "Эмулятор, красный (flag racepos300 1):"; "$PY" tests/aicar/racepos_check.py $F/${TAG}_old/smoke.txt > "$OUT/emu_red.txt"; rc=$?
grep -E "FAIL|RESULT" "$OUT/emu_red.txt" | sed 's/^/  /'
if [ $rc = 1 ] && grep -q "^RESULT FAIL" "$OUT/emu_red.txt"; then echo "  упал, как должен"; red=$((red + 1)); else echo "  КРАСНЫЙ НЕ ПОЙМАН"; fi
echo "Эмулятор, зелёный:"; "$PY" tests/aicar/racepos_check.py $F/${TAG}_new/smoke.txt | tee "$OUT/emu.txt" | sed 's/^/  /'; [ "${PIPESTATUS[0]}" = 0 ] && green=$((green + 1))
echo "Эмулятор, зелёный при прежнем пути Скиннера (flag ledgeold 1, через стену K11-4):"
"$PY" tests/aicar/racepos_check.py $F/${TAG}_ledge/smoke.txt > "$OUT/emu_ledgeold.txt"; rc=$?
grep -E "^(start|cut|back)|FAIL|RESULT" "$OUT/emu_ledgeold.txt" | sed 's/^/  /'; [ $rc = 0 ] && green=$((green + 1))
[ $red = 2 ] && [ $green = 3 ] && { echo "PASS (красные пойманы, зелёные сошлись)"; exit 0; }
echo "FAIL (красных пойманы $red из 2, зелёных $green из 3)"; exit 1
