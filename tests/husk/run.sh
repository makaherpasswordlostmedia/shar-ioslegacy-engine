#!/bin/bash
# Гейт правки 355 (остов: сесть можно, едет 4–5 м/с; оставленная машина не «призрак»): tests/husk/host.c, синтетический плоский мир —
# данных игры не нужно. Красный -DCAR_HUSK_OLD=1 обязан упасть на B1 и C2, потом зелёный.
set -u; cd "$(dirname "$0")/../.."; mkdir -p build/husk
V=viewer; SRC="tests/husk/host.c $V/car.c $V/col.c $V/traffic.c $V/homer.c $V/skin.c"
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -Wno-stringop-truncation -DSKIN_HOST -I $V"
$CC -DCAR_HUSK_OLD=1 $SRC -lm -o build/husk/red || exit 2
build/husk/red > build/husk/red.txt 2>&1
if grep -q "^FAIL B1" build/husk/red.txt && grep -q "^FAIL C2" build/husk/red.txt; then echo "красный (-DCAR_HUSK_OLD=1): упал на B1 и C2, как должен"; red=1
else echo "КРАСНЫЙ НЕ ПОЙМАН"; cat build/husk/red.txt; red=0; fi
$CC $SRC -lm -o build/husk/green || exit 2
build/husk/green | tee build/husk/green.txt; rc=${PIPESTATUS[0]}
if [ $red -eq 1 ] && [ $rc -eq 0 ]; then echo "PASS: красный пойман, зелёный"; exit 0; fi
echo "FAIL: красный $red, зелёный rc=$rc"; exit 1
