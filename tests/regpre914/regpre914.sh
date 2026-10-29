#!/bin/bash
# Гейт Б TEST57 (загрузки стоя): (1) хост-юнит tests/regpre914/unit.c на настоящей regPreMemOk из viewer/regpre.h — красный прежнее, зелёный зазор;
# (2) движок в безголовом эмуляторе: стоять у каждых ворот регионов уровня (tests/regpre914/gates.py читает их из level.shr), при свободной куче 6,8 МБ (у границы 7 МБ ворот REGPRE на железе);
# зелёный: на каждой точке REGPRE <= 2 включений и <= 1 клетки в секунду; красный: тот же прогон с файлом regprememold рядом с EBOOT обязан дать хотя бы одну плохую точку.
#   tests/regpre914/regpre914.sh [EBOOT НАБОР [УРОВЕНЬ...]]    без аргументов — только юнит; НАБОР — каталог PSP/GAME/SHARTEST15 (по умолчанию уровень 5); SMOKE_HOME — свой HOME эмулятора
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; D=tests/regpre914
BIN="${TMPDIR:-/tmp}/regpre914_unit.$$"; cc -O1 -o "$BIN" $D/unit.c -lm || { echo "ГЕЙТ Б TEST57: FAIL (юнит не собрался)"; exit 1; }
"$BIN"; u=$?; rm -f "$BIN"; [ $u = 0 ] || { echo "ГЕЙТ Б TEST57: FAIL (юнит)"; exit 1; }
[ $# -ge 2 ] || { echo "ГЕЙТ Б TEST57: PASS (только юнит)"; exit 0; }
EB=$1; SET=$2; shift 2; LV=${*:-5}; T="${TMPDIR:-/tmp}/regpre914.$$"; mkdir -p "$T"; trap 'rm -rf "$T"' EXIT
python3 $D/gates.py "$SET" > "$T/gates.json" || { echo "ГЕЙТ Б TEST57: FAIL (ворота)"; exit 1; }
bad_new=0; bad_old=0
for L in $LV; do
  python3 $D/gen.py "$T/gates.json" $L 6.8 > "$T/s.txt"
  for mode in new old; do
    R="$T/pk_$mode"; rm -rf "$R"; cp -cR "$SET" "$R" 2>/dev/null || cp -R "$SET" "$R"; cp "$EB" "$R/EBOOT.PBP"; [ $mode = old ] && : > "$R/regprememold"
    rm -f "$R/smoke.txt"; cp "$T/s.txt" "$R/scenario.txt"; touch "$R/smokelog"
    mkdir -p "$T/out_$mode"; python3 tools/smoke_headless.py "$R" "$T/out_$mode" 900 >/dev/null 2>&1; cp "$R/smoke.txt" "$T/smoke_$mode.txt" 2>/dev/null
    python3 $D/analyze.py --gates "$T/gates.json" "$T/smoke_$mode.txt" > "$T/an_$mode.txt"; rc=$?; tail -1 "$T/an_$mode.txt" | sed "s/^/L$L $mode: /"
    [ $mode = new ] && [ $rc != 0 ] && bad_new=1; [ $mode = old ] && [ $rc = 0 ] && bad_old=1
  done
done
[ $bad_new = 0 ] && [ $bad_old = 0 ] && { echo "ГЕЙТ Б TEST57: PASS (зелёный на новом, красный на regprememold)"; exit 0; }
echo "ГЕЙТ Б TEST57: FAIL (новое плохо: $bad_new, старое не поймано: $bad_old)"; exit 1
