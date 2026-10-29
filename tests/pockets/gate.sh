#!/bin/bash
# Правка Роба 339 (05.10, L1 F4-8): карманы за внутренними заборами — по опоре выше верха забора машина переезжала линию оригинала
# и оставалась там, откуда не выехать. Правка 346 (05.10, L1 K13-2): «на скорости заезжаем на эти заборы» — удар краша подбрасывал
# машину выше верха стены двора. Гейт: tests/pockets/host.c на всех уровнях + два красных.
#   tests/pockets/gate.sh [BASE]   BASE — коммит прежнего кода для красного (по умолчанию 04cf7ce^ — код до правок 339/346;
#   прежнее умолчание HEAD работало только до коммита правок: после него car.c/col.c HEAD уже содержат colFenceSupOff и
#   carCrashPopOld, и сборка с shim_old.c падала на двойных символах)
#   зелёный: A (F4-8), E (стена K13-2, таран 60–100 км/ч) и B/C/D/F (каждый уровень 1–7) — RESULT OK
#   красный 1 (флагом): POCKETS_OLD=1 — новое = прежнее, A и B обязаны упасть
#   красный 2 (прежним кодом): car.c/col.c из BASE + shim_old.c — A обязано упасть
set -u
cd "$(dirname "$0")/../.."
OUT=build/pockets; mkdir -p "$OUT"; BASE=${1:-04cf7ce^}
CC="cc -std=c11 -O2 -Wall -Wno-unused-function ${EXTRA_CFLAGS:-}"   # EXTRA_CFLAGS: бисекция флагов откатов (-DSEAM_WALL_OLD=1 ...)
$CC -I viewer tests/pockets/host.c viewer/car.c viewer/col.c -lm -o "$OUT/host" || exit 2
mkdir -p "$OUT/base"; for f in car.c car.h col.c col.h carparams.h; do git show "$BASE:viewer/$f" > "$OUT/base/$f" || exit 2; done
$CC -I "$OUT/base" -I viewer tests/pockets/host.c "$OUT/base/car.c" "$OUT/base/col.c" tests/pockets/shim_old.c -lm -o "$OUT/host_base" || exit 2
LV() { [ "$1" = 1 ] && echo build/level.shr || echo "build/levels/l$1/level.shr"; }
bad=0
"$OUT/host" build/level.shr f48 > "$OUT/f48.txt"; r=$?
grep -E "^(ok|FAIL) A" "$OUT/f48.txt"; [ $r = 0 ] || { echo "ЗЕЛЁНЫЙ A: FAIL"; bad=1; }
"$OUT/host" build/level.shr walls 250 517 30 > "$OUT/k13.txt"; r=$?
grep -E "^(ok|FAIL) E|^ИТОГ" "$OUT/k13.txt"; [ $r = 0 ] || { echo "ЗЕЛЁНЫЙ E (K13-2): FAIL"; bad=1; }
for n in ${LEVELS:-1 2 3 4 5 6 7}; do
  L=$(LV $n); [ -f "$L" ] || { echo "L$n: нет $L"; bad=1; continue; }
  "$OUT/host" "$L" census > "$OUT/census_l$n.txt"; r=$?
  echo "L$n карманы: $(grep '^ИТОГ' "$OUT/census_l$n.txt" | cut -d: -f2-) — $(grep RESULT "$OUT/census_l$n.txt")"
  [ $r = 0 ] || { grep "^FAIL\|ПЛОХО\|ТОЛЧОК\|ВЫТАЛКИВАЕТ" "$OUT/census_l$n.txt" | head -5; bad=1; }
  [ -n "${NO_WALLS:-}" ] && continue
  "$OUT/host" "$L" walls > "$OUT/walls_l$n.txt"; r=$?
  echo "L$n стены: $(grep '^ИТОГ' "$OUT/walls_l$n.txt" | cut -d: -f2-)"
  [ $r = 0 ] || { grep "^FAIL" "$OUT/walls_l$n.txt" | head -3; bad=1; }
done
if [ -z "${NO_WALLS:-}" ]; then   # F: семья «таран в стену двора» по КАЖДОМУ уровню против своей базы (16.10: сумма по уровням маскировала ухудшение L2/L5 «на стене» 4 -> 6 выигрышем L1)
  # tests/pockets/f_known.tsv: «уровень метрика максимум_нового» — известное, принятое ухудшение (up выше верха, top на стене, beh за ней, frozen замерла); сверх записанного — провал
  fbad=0; fnote=0
  for n in ${LEVELS:-1 2 3 4 5 6 7}; do
    [ -f "$OUT/walls_l$n.txt" ] || continue
    read -r ou ot ob of nu nt nb nf <<< "$(awk -F'\t' '/^WALLS/ {print $2, $3, $4, $5, $6, $7, $8, $9}' "$OUT/walls_l$n.txt")"
    line="F L$n стены: выше верха $ou -> $nu, на стене $ot -> $nt, за ней $ob -> $nb, замерла $of -> $nf"
    for m in up:$ou:$nu top:$ot:$nt beh:$ob:$nb frozen:$of:$nf; do
      IFS=: read -r name o w <<< "$m"
      if [ "$w" -gt "$o" ]; then
        k=$(awk -F'\t' -v l="$n" -v m="$name" '$1 == l && $2 == m {print $3}' tests/pockets/f_known.tsv 2>/dev/null)
        if [ -n "$k" ] && [ "$w" -le "$k" ]; then line="$line | известное: $name $o -> $w (f_known.tsv, до $k)"; fnote=1
        else line="$line | ХУЖЕ: $name $o -> $w"; fbad=1; fi
      fi
    done
    echo "$line"
  done
  if [ "$fbad" = 0 ]; then echo "ok F: каждый уровень не хуже своей базы$([ $fnote = 1 ] && echo ' (кроме записанного в f_known.tsv)')"; else echo "FAIL F"; bad=1; fi
fi
POCKETS_OLD=1 "$OUT/host" build/level.shr f48 > "$OUT/red_flag_f48.txt"; r1=$?
POCKETS_OLD=1 "$OUT/host" build/level.shr census > "$OUT/red_flag_census_l1.txt"; r2=$?
POCKETS_OLD=1 "$OUT/host" build/level.shr walls 250 517 30 > "$OUT/red_flag_k13.txt" || r2=$((r2 + 100))
if [ $r1 != 0 ] && [ $r2 -ge 100 ] && [ $((r2 % 100)) != 0 ]; then echo "красный 1 (POCKETS_OLD=1): A, B и E упали, как должны — $(grep '^ИТОГ' "$OUT/red_flag_census_l1.txt" | cut -d: -f2-)"
else echo "КРАСНЫЙ 1 НЕ ПОЙМАН (POCKETS_OLD=1): A rc $r1, B+E rc $r2"; bad=1; fi
"$OUT/host_base" build/level.shr f48 > "$OUT/red_base_f48.txt"; r3=$?
"$OUT/host_base" build/level.shr walls 250 517 30 > "$OUT/red_base_k13.txt"; r4=$?
if [ $r3 != 0 ] && grep -q "^FAIL A: новое" "$OUT/red_base_f48.txt" && [ $r4 != 0 ] && grep -q "^FAIL E: новое" "$OUT/red_base_k13.txt"; then
  echo "красный 2 (код $BASE без правок): F4-8 — $(grep 'итог A' "$OUT/red_base_f48.txt" | tail -1 | sed 's/^ *//'); K13-2 — $(grep '^ИТОГ' "$OUT/red_base_k13.txt" | sed 's/.*новое — //') — упал, как должен"
else echo "КРАСНЫЙ 2 НЕ ПОЙМАН (код $BASE): A rc $r3, E rc $r4"; bad=1; fi
[ $bad = 0 ] && echo "pockets gate: PASS" || echo "pockets gate: FAIL"
exit $bad
