#!/bin/bash
# Ночь ботов 03.10: цель тарана миссии получает полный урон машина-машина, трафик — × CAR_HIT_DMG_K (tests/aicar/m3dmg_host.c).
# Сначала красный: -DMC_HIT_DMG_TRAFFIC=1 (машине миссии урон как у трафика) обязан упасть; потом зелёный.
cd "$(dirname "$0")/../.."
OUT=build/aicar; mkdir -p "$OUT"; V=viewer
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V"
SRC="tests/aicar/m3dmg_host.c $V/msncar.c $V/car.c $V/col.c $V/traffic.c $V/homer.c $V/skin.c"
$CC -DMC_HIT_DMG_TRAFFIC=1 $SRC -lm -o "$OUT/m3dmg_red" 2> "$OUT/m3dmg_build.txt" || { echo "FAIL: сборка (красный)"; head -5 "$OUT/m3dmg_build.txt"; exit 1; }
if "$OUT/m3dmg_red" > "$OUT/m3dmg_red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; else echo "красный: $(grep -m1 'CHECK.*FAIL' "$OUT/m3dmg_red.txt" | cut -c1-140)"; red=1; fi
$CC $SRC -lm -o "$OUT/m3dmg" 2> "$OUT/m3dmg_build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/m3dmg_build.txt"; exit 1; }
echo "зелёный:"; "$OUT/m3dmg" | grep -E "CHECK|RESULT"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
