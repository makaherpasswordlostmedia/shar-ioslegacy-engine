#!/bin/bash
# Гейт правки 199 (взрыв машины через 3 с после разбития, разбитая не едет): tests/boom/host.c. Сначала КРАСНЫЙ —
# -DCAR_BOOM_DELAY=0 (прежний мгновенный взрыв) обязан упасть на «A», потом ЗЕЛЁНЫЙ.
set -u; cd "$(dirname "$0")/../.."; mkdir -p build/boom
cc -std=c11 -O2 -I viewer -DCAR_BOOM_DELAY=0 tests/boom/host.c viewer/car.c viewer/col.c -lm -o build/boom/red || exit 2
build/boom/red build/level.shr > build/boom/red.txt 2>&1; rr=$?
if [ $rr -ne 0 ] && grep -q "^FAIL A:" build/boom/red.txt; then echo "красный (-DCAR_BOOM_DELAY=0): упал, как должен"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; fi
cc -std=c11 -O2 -I viewer -DCAR_DEAD_DRIVES=1 tests/boom/host.c viewer/car.c viewer/col.c -lm -o build/boom/red2 || exit 2
build/boom/red2 build/level.shr > build/boom/red2.txt 2>&1; rr=$?
if [ $rr -ne 0 ] && grep -q "^FAIL B:" build/boom/red2.txt; then echo "красный (-DCAR_DEAD_DRIVES=1): упал, как должен"; red=$((red + 1)); else echo "КРАСНЫЙ НЕ ПОЙМАН (B)"; fi
cc -std=c11 -O2 -I viewer tests/boom/host.c viewer/car.c viewer/col.c -lm -o build/boom/green || exit 2
build/boom/green build/level.shr | tee build/boom/green.txt | tail -5; rc=${PIPESTATUS[0]}
if [ $red -eq 2 ] && [ $rc -eq 0 ]; then echo "PASS: красный 2/2 пойман, зелёный"; exit 0; fi
echo "FAIL: красный $red/2, зелёный rc=$rc"; exit 1
