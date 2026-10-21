#!/bin/bash
# Правка 176: урон машин трафика от удара машины Гомера (tests/trafhit/host.c). Сначала красный: -DCAR_HIT_DMG_K=1 (прежний урон)
# обязан упасть; потом зелёный.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/trafhit; mkdir -p "$OUT"; CC="cc -O2 -std=c11 -Wall -Wno-unused-function -I viewer"
$CC -DCAR_HIT_DMG_K=1.f tests/trafhit/host.c viewer/car.c viewer/col.c -lm -o "$OUT/red" || exit 2
if "$OUT/red" > "$OUT/red.txt" 2>&1; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; else echo "красный: $(grep -m1 'CHECK.*FAIL' "$OUT/red.txt" | cut -c1-100)"; red=1; fi
$CC -DCAR_RAM_DMG_K=1.f tests/trafhit/host.c viewer/car.c viewer/col.c -lm -o "$OUT/red185" || exit 2   # правка 185: урон таранов без доли
if "$OUT/red185" > "$OUT/red185.txt" 2>&1; then echo "КРАСНЫЙ 185 НЕ ПОЙМАН"; red=0; else echo "красный 185: $(grep -m1 'CHECK ram.*FAIL' "$OUT/red185.txt" | cut -c1-110)"; fi
$CC tests/trafhit/host.c viewer/car.c viewer/col.c -lm -o "$OUT/green" || exit 2
echo "зелёный:"; "$OUT/green" | grep -E "CHECK|RESULT"; green=${PIPESTATUS[0]}
[ $red = 1 ] && [ $green = 0 ] && echo "PASS (красный пойман, зелёный сошёлся)" || { echo "FAIL"; exit 1; }
