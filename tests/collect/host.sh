#!/bin/bash
# Гейт В5 (карточки, осы, гэги уровня 1) на Маке: сначала КРАСНЫЙ — те же проверки на испорченном пакете (карточка
# сдвинута, триггеры гэгов сдвинуты/сужены, точки ос сдвинуты) обязаны упасть; потом ЗЕЛЁНЫЙ на настоящем пакете.
#   tests/collect/host.sh [PACK]      по умолчанию build/collect-l1.shr (tools/collect_export.py), уровень build/level.shr
# Ожидания — прямо из данных диска, независимо от экспортёра (tests/collect/expect.py). Итог: build/collect/host_*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PACK="${1:-build/collect-l1.shr}"; OUT=build/collect; mkdir -p "$OUT"
[ -f "$PACK" ] || { echo "FAIL: нет $PACK (python3 tools/collect_export.py)"; exit 1; }
. .venv/bin/activate
python3 tests/collect/expect.py > "$OUT/expect.tsv" || { echo "FAIL: expect.py"; exit 1; }
V=viewer
. tools/bots/lib.sh; LIB="$BOTS_LIB"   # общий список исходников мира (tools/bots/lib.sh)
cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots tests/collect/host.c $LIB -lm \
   -o "$OUT/host" 2> "$OUT/build.txt" || { echo "FAIL: сборка"; head -5 "$OUT/build.txt"; exit 1; }
run() { BW_COLLECT="$PACK" "$OUT/host" "$OUT/expect.tsv" "$PACK" build/level.shr build/homer.shr "$@"; }
red=0
for p in card gag trig wasp; do
  run --plant "$p" > "$OUT/host_plant_$p.txt" 2>&1; rc=$?
  f=$(grep -c "FAIL" "$OUT/host_plant_$p.txt")
  if [ $rc -ne 0 ]; then echo "красный ($p испорчен): упал, как должен — $(grep -m1 'CHECK.*FAIL' "$OUT/host_plant_$p.txt" | cut -c1-110)"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН: испорченный $p прошёл гейт"; fi
done
run > "$OUT/host_green.txt" 2>&1; rc=$?
grep "^CHECK\|^RESULT" "$OUT/host_green.txt"
if [ $red -eq 4 ] && [ $rc -eq 0 ]; then echo "PASS: красный 4/4 пойман, зелёный $(grep -m1 RESULT "$OUT/host_green.txt" | cut -d' ' -f3)"; exit 0; fi
echo "FAIL: красный $red/4, зелёный rc=$rc"; exit 1
