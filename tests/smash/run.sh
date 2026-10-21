#!/bin/bash
# Гейт правки Роба 297 (04.10, трамплин у L1 K2-6: «квадратные стоги сена — у оригинала разбиваются, у нас неразбиваемые»).
# Мак, без эмулятора: tests/smash/host.c на настоящих car.c/col.c/props.c/stateprops.c, все уровни.
# Сначала КРАСНЫЙ: сборка с -DSP_HIT_MINAXIS=1 (прежняя ось удара: наименьшее перекрытие в плане) обязана упасть на каждом
# уровне, где есть предметы (посадка сверху: было 2–12 % разбитых), потом ЗЕЛЁНЫЙ.
#   tests/smash/run.sh [level.shr ...]   (по умолчанию build/level.shr и build/levels/l2..l7/level.shr)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/smash; mkdir -p "$OUT"
LEVELS=("$@"); [ ${#LEVELS[@]} -eq 0 ] && { LEVELS=(build/level.shr); for n in 2 3 4 5 6 7; do [ -f build/levels/l$n/level.shr ] && LEVELS+=(build/levels/l$n/level.shr); done; }
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer"
SRC="tests/smash/host.c viewer/props.c viewer/stateprops.c viewer/col.c viewer/car.c viewer/coins.c -lm"
$CC $SRC -o "$OUT/host-new" || exit 2
$CC -DSP_HIT_MINAXIS=1 $SRC -o "$OUT/host-old" || exit 2
fail=0
for lvl in "${LEVELS[@]}"; do
  n=$(basename "$(dirname "$lvl")"); [ "$lvl" = build/level.shr ] && n=l1
  "$OUT/host-old" "$lvl" > "$OUT/red_$n.txt" 2>&1
  if [ $? -ne 0 ]; then echo "красный $n (прежняя ось удара): упал, как должен — $(grep -o 'сверху [0-9]* из [0-9]* ([0-9.]* %)' "$OUT/red_$n.txt")"
  elif grep -q 'экземпляров 0;\|нет стейтпропов' "$OUT/red_$n.txt"; then echo "красный $n: предметов нет — не применим"
  else echo "КРАСНЫЙ НЕ ПОЙМАН: $n с прежней осью удара прошёл"; fail=1; fi
  "$OUT/host-new" "$lvl" > "$OUT/green_$n.txt" 2>&1; rc=$?
  cat "$OUT/green_$n.txt"
  [ $rc -eq 0 ] || { echo "ЗЕЛЁНЫЙ НЕ ПРОШЁЛ: $n"; fail=1; }
done
[ $fail -eq 0 ] && { echo "PASS: красный пойман, зелёный"; exit 0; }
echo "FAIL"; exit 1
