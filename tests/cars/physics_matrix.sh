#!/bin/bash
# Матрица физики машины на одном срезе исходников, одни данные уровня и одни входы для всех срезов.
#   tests/cars/physics_matrix.sh OUT [LEVEL]   (запускать из корня среза: основное дерево или worktree)
# Строка matrix.tsv: проверка, код возврата, итог. Пороги и эталоны берутся из самих проверок, здесь не задаются.
# cornering_ai: потолок переворотов 10 (был 7) с f823de9d (10.10, у водителей миссий незаданные команды .con берутся из .con самой машины,
# слово Роба «у каждой машины своя физика»): +3 переворота из 190 экстремальных заездов (полный руль на газу 110–145 км/ч у высоких marge_v, cletu_v,
# minivana, nuctruck; -DCAR_TUNING_PERCAR_OLD=1 даёт прежние 7). Высокие машины — №452 «так оставить».
# Трамплины — с известными расхождениями tests/jumps/ramps_known.tsv (по слову Роба 08.10 22:4x: точечные исключения, чтобы
# закрыть наряд; строгий счёт «вне допуска» печатается той же строкой). NATIVE_RAM/NATIVE_TRACE — входы native_inertia.sh.
set -u
cd "$(dirname "$0")/../.."
mkdir -p "$1"; OUT=$(cd "$1" && pwd)
L=${2:-build/level.shr}; LEVEL=$(cd "$(dirname "$L")" && pwd)/$(basename "$L")
M="$OUT/matrix.tsv"; : > "$M"
matrix_bad=0
row() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$M"; printf '%-10s rc=%-3s %s\n' "$1" "$2" "$3"; [ "$2" = 0 ] || matrix_bad=1; }
{ git rev-parse HEAD; git status --short -- viewer tests tools; } > "$OUT/head.txt"
shasum -a 256 "$LEVEL" viewer/car.c viewer/car.h viewer/col.c viewer/col.h > "$OUT/sha.txt"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -I viewer"
HOST="viewer/props.c viewer/stateprops.c viewer/coins.c"

$CC tests/humps/host.c viewer/car.c viewer/col.c -lm -o "$OUT/humps" 2>"$OUT/humps.cc" \
  && "$OUT/humps" "$LEVEL" > "$OUT/humps.log"; r=$?
row humps $r "$(grep -c '^FAIL' "$OUT/humps.log" 2>/dev/null) FAIL; $(grep -E '^  (горбы наискось|стены):' "$OUT/humps.log" | sed 's/^  //' | tr '\n' ' ')"

$CC -DSKIN_HOST tests/jumps/twin.c viewer/car.c viewer/col.c $HOST -lm -o "$OUT/twin" 2>"$OUT/twin.cc" \
  && "$OUT/twin" "$LEVEL" > "$OUT/jumps-strict.log"; r=$?
row jumps $r "$(tail -1 "$OUT/jumps-strict.log")"

OUT_DIR="$OUT/crash" tests/airwalls/crash.sh "$LEVEL" > "$OUT/crash.log" 2>&1; r=$?
row crash $r "$(grep -E '^(J11-9|F12-6L|F12-6R):' "$OUT/crash.log" | sed 's/порт.*), //' | tr '\n' ' ')$(tail -1 "$OUT/crash.log")"

$CC -DSKIN_HOST tests/ramps/host.c viewer/car.c viewer/col.c $HOST -lm -o "$OUT/ramps" 2>"$OUT/ramps.cc" \
  && "$OUT/ramps" "$LEVEL" > "$OUT/ramps.log"; r=$?
row ramps $r "$(tail -1 "$OUT/ramps.log")"

$CC tests/carpair/host.c viewer/car.c viewer/col.c -lm -o "$OUT/carpair" 2>"$OUT/carpair.cc" \
  && "$OUT/carpair" "$LEVEL" > "$OUT/carpair.log"; r=$?
row carpair $r "$(tail -1 "$OUT/carpair.log")"

cc -O2 -std=c99 -Wall -I viewer tests/foliage/host.c viewer/car.c viewer/col.c -lm -o "$OUT/foliage" 2>"$OUT/foliage.cc" \
  && "$OUT/foliage" "$LEVEL" > "$OUT/foliage.log"; r=$?
row foliage $r "$(tail -1 "$OUT/foliage.log")"

OUT_DIR="$OUT/landing" bash tests/cars/landing_timer.sh > "$OUT/landing.log" 2>&1; r=$?
row landing $r "$(head -1 "$OUT/landing.log") | $(tail -1 "$OUT/landing.log")"

OUT_DIR="$OUT/suspension" bash tests/cars/suspension.sh > "$OUT/suspension.log" 2>&1; r=$?
row suspension $r "$(tail -1 "$OUT/suspension.log")"

OUT_DIR="$OUT/inertia" bash tests/cars/native_inertia.sh > "$OUT/inertia.log" 2>&1; r=$?
row inertia $r "$(tail -1 "$OUT/inertia.log")"

# №406 (09.10): повороты всего флота (перевороты не больше уровня прежнего порта) и положение кузова famil_v против записей PS2.
# Каждая строка со своим красным контролем: он обязан провалиться, иначе строка красная.
$CC tests/cars/cornering.c viewer/car.c viewer/col.c -lm -o "$OUT/cornering" 2>"$OUT/cornering.cc" \
  && "$OUT/cornering" --max-flips 7 > "$OUT/cornering.log"; r=$?
$CC -DCAR_TYRE_LEVER_OLD=1 -DCAR_WEEBLE_GROUND_OLD=1 tests/cars/cornering.c viewer/car.c viewer/col.c -lm -o "$OUT/cornering_red" 2>>"$OUT/cornering.cc" \
  && "$OUT/cornering_red" --max-flips 7 > "$OUT/cornering_red.log"; rr=$?
[ $rr != 0 ] || r=9
row cornering $r "$(tail -1 "$OUT/cornering.log") | красный Fable: $(tail -1 "$OUT/cornering_red.log")"

$CC tests/cars/attitude.c viewer/car.c viewer/col.c -lm -o "$OUT/attitude" 2>"$OUT/attitude.cc" \
  && "$OUT/attitude" > "$OUT/attitude.log"; r=$?
red=""
for k in "-DCAR_TYRE_HUB_OLD=1" "-DCAR_TYRE_LEVER_OLD=1 -DCAR_WEEBLE_GROUND_OLD=1" "-DCAR_BRAKE_PLUS3_OLD=1" "-DCAR_GAS_GRIP_OLD=1"; do
  $CC $k tests/cars/attitude.c viewer/car.c viewer/col.c -lm -o "$OUT/attitude_red" 2>>"$OUT/attitude.cc" \
    && "$OUT/attitude_red" > "$OUT/attitude_red.log"; rr=$?
  red="$red [$k: $(tail -1 "$OUT/attitude_red.log")]"; [ $rr != 0 ] || r=9
done
row attitude $r "$(tail -1 "$OUT/attitude.log") |$red"

# Аудит 09.10, п. 6: прочность машины игрока о стены — тот же бот, что у близнеца boom.py (PS2: разбита 12-м ударом).
$CC tests/cars/boom_ps2.c viewer/car.c viewer/col.c -lm -o "$OUT/boom_ps2" 2>"$OUT/boom_ps2.cc" \
  && "$OUT/boom_ps2" "$LEVEL" > "$OUT/boom_ps2.log"; r=$?
$CC -DCAR_WALL_DMG_OLD=1 tests/cars/boom_ps2.c viewer/car.c viewer/col.c -lm -o "$OUT/boom_ps2_red" 2>>"$OUT/boom_ps2.cc" \
  && "$OUT/boom_ps2_red" "$LEVEL" > "$OUT/boom_ps2_red.log"; rr=$?
[ $rr != 0 ] || r=9
row boom_ps2 $r "$(head -1 "$OUT/boom_ps2.log" | cut -c1-90) | красный: $(head -1 "$OUT/boom_ps2_red.log" | cut -c1-60)"

# Аудит 09.10 п. 49: машины ИИ и миссий (95 пар кузов + .con водителя из AddStageVehicle L1–L7) в повороте. Порог — уровень этой
# правки (перевороты 7, крен внутрь 4 из 190), страховка от регресса: PS2 по машинам ИИ нет (В102). Красные: Fable до 406 (70
# переворотов), 406 (крен внутрь у 118).
$CC tests/cars/cornering_ai.c viewer/car.c viewer/col.c viewer/mission/msn_file.c viewer/mission/msn_ops.c -lm -o "$OUT/cornering_ai" 2>"$OUT/cornering_ai.cc" \
  && "$OUT/cornering_ai" build/missions/level0{1,2,3,4,5,6,7}.msn --max-flips 10 --max-inward 4 > "$OUT/cornering_ai.log"; r=$?
red=""
for k in "-DCAR_TYRE_LEVER_OLD=1 -DCAR_WEEBLE_GROUND_OLD=1" "-DCAR_TYRE_HUB_OLD=1"; do
  $CC $k tests/cars/cornering_ai.c viewer/car.c viewer/col.c viewer/mission/msn_file.c viewer/mission/msn_ops.c -lm -o "$OUT/cornering_ai_red" 2>>"$OUT/cornering_ai.cc" \
    && "$OUT/cornering_ai_red" build/missions/level0{1,2,3,4,5,6,7}.msn --max-flips 10 --max-inward 4 > "$OUT/cornering_ai_red.log"; rr=$?
  red="$red [$k: $(tail -1 "$OUT/cornering_ai_red.log")]"; [ $rr != 0 ] || r=9
done
row cornering_ai $r "$(tail -1 "$OUT/cornering_ai.log") |$red"
# накат famil_v против PS2 на 10/20/28 м/с (Стенд 16.10, tests/cars/coast_ps2.c); красный -DCAR_COAST_LIN=0 (прежнее сопротивление и без газа) обязан упасть
$CC tests/cars/coast_ps2.c viewer/car.c viewer/col.c -lm -o "$OUT/coast" 2>"$OUT/coast.cc" && "$OUT/coast" > "$OUT/coast.log"; r=$?
$CC -DCAR_COAST_LIN=0 tests/cars/coast_ps2.c viewer/car.c viewer/col.c -lm -o "$OUT/coast_red" 2>>"$OUT/coast.cc" && "$OUT/coast_red" > "$OUT/coast_red.log"; rr=$?
[ $rr != 0 ] || r=9
row coast $r "$(tail -1 "$OUT/coast.log") | красный (LIN=0): $(tail -1 "$OUT/coast_red.log")"
# скользящий удар о стену высоких машин (В102, PS2 marge_v/schoolbu 35°/10 м/с): нос не клюёт, два колеса не поднимаются; красный -DCAR_HITY_OLD=1 обязан упасть
$CC tests/cars/wallslide.c viewer/car.c viewer/col.c -lm -o "$OUT/wallslide" 2>"$OUT/wallslide.cc" && "$OUT/wallslide" > "$OUT/wallslide.log"; r=$?
$CC -DCAR_HITY_OLD=1 tests/cars/wallslide.c viewer/car.c viewer/col.c -lm -o "$OUT/wallslide_red" 2>>"$OUT/wallslide.cc" && "$OUT/wallslide_red" > "$OUT/wallslide_red.log"; rr=$?
[ $rr != 0 ] || r=9
row wallslide $r "$(tail -1 "$OUT/wallslide.log") | красный (HITY_OLD): $(tail -1 "$OUT/wallslide_red.log")"
# файл rollps2 (крен ближе к PS2): ROLLG=0,22 — famil_v крен ≥ 0,17°/(м/с²) наружу и рыскание в квартилях PS2; красный ROLLG=0,1 (мало) обязан упасть; без файла строка attitude выше прежняя
$CC tests/cars/attitude.c viewer/car.c viewer/col.c -lm -o "$OUT/attitude_roll" 2>"$OUT/rollps2.cc" && ROLLG=0.22 "$OUT/attitude_roll" > "$OUT/rollps2.log"; r=$?
ROLLG=0.1 "$OUT/attitude_roll" > "$OUT/rollps2_red.log"; rr=$?; [ $rr != 0 ] || r=9
row rollps2 $r "$(grep ' R rollps2' "$OUT/rollps2.log" | cut -c1-140) | красный (0,1): $(tail -1 "$OUT/rollps2_red.log")"
if [ "$matrix_bad" = 0 ]; then echo "physics matrix: PASS 16/16"; else echo "physics matrix: FAIL (see matrix.tsv)"; fi
exit "$matrix_bad"
