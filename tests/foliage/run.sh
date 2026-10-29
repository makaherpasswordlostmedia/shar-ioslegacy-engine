#!/bin/bash
# Гейт правки Роба 71 (повтор 01.10: «кусты выбрасывают в разные стороны; в оригинале с кустами проблем не было никогда»).
# Мак, без эмулятора: настоящая физика viewer/car.c + viewer/col.c на данных уровня.
#   host.c   — изгородь у первого стекла: удар сбоку (30/60 кадров), посадка днищем 2/5/10 м, крыша рядом, въезд на уровне
#   hedges.c — все лежачие кусты уровня: въезд 5/10/15 м/с под 0/30/60° с обеих сторон (подброс, отскок, разгон, разворот,
#              переезд низкой изгороди без забора)
# Сначала КРАСНЫЙ: та же проверка с прежней реакцией куста (-DFOLIAGE_PREV: подскок сбоку до 7 м/с, посадка до 2.5 м/с,
# упругость 0.4, низкая изгородь — стена) обязана упасть. Потом ЗЕЛЁНЫЙ.
#   tests/foliage/run.sh [level.shr ...]   (по умолчанию build/level.shr; можно несколько уровней-файлов)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/foliage; mkdir -p "$OUT"
LEVELS=("$@"); [ ${#LEVELS[@]} -eq 0 ] && LEVELS=(build/level.shr)
CC="cc -O2 -std=c11 -Wall -I viewer"
fail=0
for v in prev nopass new; do   # nopass — правка 173: мягкая преграда без проезда (как до 01.10) обязана упасть
  def=""; [ $v = prev ] && def="-DFOLIAGE_PREV"; [ $v = nopass ] && def="-DCAR_FOLIAGE_PASS=0"
  $CC $def tests/foliage/host.c viewer/car.c viewer/col.c -lm -o "$OUT/host-$v" || exit 2
  $CC $def tests/foliage/hedges.c viewer/car.c viewer/col.c -lm -o "$OUT/hedges-$v" || exit 2
done
$CC -DCOL_FOL_FENCE_KEEP=0 tests/foliage/hedges.c viewer/car.c viewer/col.c -lm -o "$OUT/hedges-nokeep" || exit 2
for lvl in "${LEVELS[@]}"; do
  n=$(basename "$lvl" .shr)
  for t in host hedges; do
    "$OUT/$t-prev" "$lvl" > "$OUT/red_${t}_$n.txt" 2>&1
    if [ $? -ne 0 ]; then echo "красный $t ($n, прежняя реакция куста): упал, как должен — $(tail -1 "$OUT/red_${t}_$n.txt")"
    else echo "КРАСНЫЙ НЕ ПОЙМАН: $t ($n) с прежней реакцией прошёл"; fail=1; fi
  done
  "$OUT/host-nopass" "$lvl" > "$OUT/red_nopass_$n.txt" 2>&1   # проезд сквозь куст проверяет host
  if [ $? -ne 0 ]; then echo "красный host ($n, куст без проезда): упал, как должен — $(grep -m1 'not crossed\|landed' "$OUT/red_nopass_$n.txt" | cut -c1-80)"
  else echo "КРАСНЫЙ НЕ ПОЙМАН: host ($n) без проезда прошёл"; fail=1; fi
  if [ "$n" = level ]; then   # правка 304: забор-изгородь без памяти пропуска — у cyl 61 L1 кузов выбрасывало на 2 м вверх
    "$OUT/hedges-nokeep" "$lvl" > "$OUT/red_nokeep_$n.txt" 2>&1
    if [ $? -ne 0 ]; then echo "красный hedges ($n, забор-изгородь без памяти): упал, как должен — $(grep -m1 '^FAIL cyl' "$OUT/red_nokeep_$n.txt" | cut -c1-90)"
    else echo "КРАСНЫЙ НЕ ПОЙМАН: hedges ($n) без памяти забора-изгороди прошёл"; fail=1; fi
  fi
  for t in host hedges; do
    "$OUT/$t-new" "$lvl" > "$OUT/green_${t}_$n.txt" 2>&1; rc=$?
    grep -E "^(FAIL|PASS|hedges:|hard neighbour)" "$OUT/green_${t}_$n.txt" | tail -4
    [ $rc -eq 0 ] || { echo "ЗЕЛЁНЫЙ НЕ ПРОШЁЛ: $t ($n)"; fail=1; }
  done
done
bash tests/foliage/cover.sh "$@" || fail=1   # правка 304: вязкость листвы — по доле кузова в кусте (все уровни по умолчанию)
[ $fail -eq 0 ] && { echo "PASS: красный пойман, зелёный"; exit 0; }
echo "FAIL"; exit 1
