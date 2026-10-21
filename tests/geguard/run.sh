#!/bin/bash
# Гейт проверки матриц перед видеочипом (viewer/geguard.c): зелёный — tests/geguard/host.c проходит; красный — с -DGEGUARD_OLD падает
set -u; cd "$(dirname "$0")"; OUT=../../build/gates/geguard; mkdir -p "$OUT"
cc -O2 -o "$OUT/host" host.c -lm && cc -O2 -DGEGUARD_OLD -o "$OUT/host_old" host.c -lm || { echo "FAIL: сборка"; exit 1; }
if "$OUT/host_old" > "$OUT/red.txt"; then echo "КРАСНЫЙ НЕ ПОЙМАН: без проверки гейт зелёный"; cat "$OUT/red.txt"; exit 1; fi
echo "красный (GEGUARD_OLD): упал, как должен — $(tail -1 "$OUT/red.txt")"
"$OUT/host" > "$OUT/green.txt" || { echo "FAIL:"; cat "$OUT/green.txt"; exit 1; }
echo "зелёный: NaN, бесконечность и мусор не проходят, обычные матрицы проходят"; echo PASS
