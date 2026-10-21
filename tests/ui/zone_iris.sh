#!/bin/bash
# №349 ирис на возврат из зоны DEATH: tests/ui/zone_iris.sh НАБОР EBOOT_НОВЫЙ EBOOT_СТАРЫЙ(-DZONE_IRIS_OLD=1). Зелёный: DEATH ... iris=1; красный: iris=0
set -u; cd "$(dirname "$0")/../.."; fail=0
for v in new old; do
  E=$2; [ $v = old ] && E=$3; T=build/zone_iris_$v; rm -rf $T; cp -c -R "$1" $T; cp -f "$E" $T/EBOOT.PBP
  L=$(SHIP_LEVELS=1 SMOKE_HEADLESS=1 SMOKE_FILEDATA="meaudio=3" SMOKE_SCN=$PWD/tests/ui/zone_iris_scenario.txt SMOKE_MAXT=200 tools/smoke.sh $PWD/$T 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
  D=$(grep -m1 "^DEATH " $R/smoke.txt); echo "$v: ${D:-нет строки DEATH} ($R)"
  if [ $v = new ]; then echo "$D" | grep -q " iris=1 " || fail=1; else echo "$D" | grep -q " iris=0 " || fail=1; fi
done
[ $fail = 0 ] && echo "PASS zone_iris" || echo "FAIL zone_iris"; exit $fail
