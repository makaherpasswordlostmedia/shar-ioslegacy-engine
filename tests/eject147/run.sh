#!/bin/bash
# Гейт правки Роба 147 (выброс взрывом как в оригинале: задержка в остове, полёт головой вперёд, касание грудью, hom_get_up):
# харнесс tests/homer/host.sh (viewer/homer.c + мир уровня, Мак, CPU), проверки «147: …» в разделе 5в.
# Сначала КРАСНЫЙ — обязаны упасть: прежний выброс (-DHOMER_EJECT_V1: сразу, спиной вперёд, вертикально — «сразу на ногах»)
# и наклон без опоры (-DHOMER_EJECT_NOCLAMP: тело уходит в землю). Потом ЗЕЛЁНЫЙ. Итог: build/eject147/*.txt
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT=build/eject147; mkdir -p "$OUT"
red=0
for plant in "-DHOMER_EJECT_V1:147: still in the burning car" "-DHOMER_EJECT_NOCLAMP:147: body never below ground"; do
  f=${plant%%:*}; want=${plant#*:}; n=${f#-D}
  HOST_CFLAGS=$f bash tests/homer/host.sh > "$OUT/red_$n.txt" 2>&1; rc=$?
  if [ $rc -ne 0 ] && grep -q "^FAIL $want" "$OUT/red_$n.txt"; then
    echo "красный ($f): упал, как должен — $(grep -c '^FAIL 147' "$OUT/red_$n.txt") проверок 147, в т.ч. «${want}»"; red=$((red + 1))
  else echo "КРАСНЫЙ НЕ ПОЙМАН: $f (rc=$rc)"; fi
done
bash tests/homer/host.sh > "$OUT/green.txt" 2>&1; rc=$?
grep "^FAIL\|147\|PASSED\|FAILED" "$OUT/green.txt"
if [ $red -eq 2 ] && [ $rc -eq 0 ]; then echo "PASS: красный 2/2 пойман, зелёный — все проверки харнесса Гомера"; exit 0; fi
echo "FAIL: красный $red/2, зелёный rc=$rc"; exit 1
