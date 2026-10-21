#!/bin/bash
# №739 (PSP висла на выходе при работающем звуке): tests/sound/exit739.sh НАБОР EBOOT_НОВЫЙ EBOOT_СТАРЫЙ(-DEXIT739_OLD=1)
# Зелёный: после END в журнале строка «EXIT739 safe sound=off»; красный: старый выход (система сразу) — строки нет. На железе — тур Роба, выход без зависания.
set -u; cd "$(dirname "$0")/../.."; fail=0
for v in new old; do
  E=$2; [ $v = old ] && E=$3; T=build/exit739_$v; rm -rf $T; cp -c -R "$1" $T; cp -f "$E" $T/EBOOT.PBP
  L=$(SHIP_LEVELS=1 SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN=$PWD/tests/sound/exit739_scenario.txt SMOKE_MAXT=120 tools/smoke.sh $PWD/$T 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
  X=$(grep -m1 "^EXIT739" $R/smoke.txt); echo "$v: ${X:-нет строки EXIT739} ($R)"
  if [ $v = new ]; then [ -n "$X" ] || fail=1; else [ -z "$X" ] || fail=1; fi
done
[ $fail = 0 ] && echo "PASS exit739" || echo "FAIL exit739"; exit $fail
