#!/bin/bash
# Ночь ботов 03.10: цель тарана миссии получает полный урон машина-машина, трафик — × CAR_HIT_DMG_K (tests/aicar/police_dmg_host.c).
# Сначала красный: -DPOLICE_DMG_OLD=1 (машине миссии урон как у трафика) обязан упасть; потом зелёный.
cd "$(dirname "$0")/../.."
OUT=build/aicar; mkdir -p "$OUT"; V=viewer
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V"
SRC="tests/aicar/police_dmg_host.c $V/msncar.c $V/car.c $V/col.c $V/traffic.c $V/homer.c $V/skin.c"
$CC -DPOLICE_DMG_OLD=1 $SRC -lm -o "$OUT/policedmg_red" 2> "$OUT/policedmg_build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/policedmg_build.txt"; exit 1; }
if "$OUT/policedmg_red" > "$OUT/policedmg_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; else echo "красный: $(grep -m1 'CHECK.*FAIL' "$OUT/policedmg_red.txt" | cut -c1-140)"; red=1; fi
$CC $SRC -lm -o "$OUT/policedmg" 2> "$OUT/policedmg_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/policedmg_build.txt"; exit 1; }
echo "зелёный:"; "$OUT/policedmg" | grep -E "CHECK|RESULT"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
