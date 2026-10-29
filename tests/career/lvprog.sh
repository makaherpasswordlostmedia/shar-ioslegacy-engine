#!/bin/bash
# Облако 05.10 (карьера): прогресс миссий всех уровней в записи (tests/career/lvprog_host.c, только viewer/savegame.c, без диска).
# Сначала красный: -DSV_BROKEN_LV=1 (поле не пишется, как до 05.10) обязан упасть; потом зелёный.
cd "$(dirname "$0")/../.."
OUT=build/career; mkdir -p "$OUT"; V=viewer
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I $V"
SRC="tests/career/lvprog_host.c $V/savegame.c"
$CC -DSV_BROKEN_LV=1 $SRC -lm -o "$OUT/lvprog_red" 2> "$OUT/lvprog_build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/lvprog_build.txt"; exit 1; }
if "$OUT/lvprog_red" > "$OUT/lvprog_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; else echo "красный: $(grep -c 'CHECK.*FAIL' "$OUT/lvprog_red.txt") провал(а): $(grep -m1 'CHECK.*FAIL' "$OUT/lvprog_red.txt" | cut -c1-140)"; red=1; fi
$CC $SRC -lm -o "$OUT/lvprog" 2> "$OUT/lvprog_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/lvprog_build.txt"; exit 1; }
echo "зелёный:"; "$OUT/lvprog" | grep -E "CHECK|RESULT"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
