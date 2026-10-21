#!/bin/bash
# Все гейты механик уровней 2–7 на Маке (без эмулятора): покрытие команд, барьеры, летающие актёры, AddSafeZone, щиты ос, обезьяны.
# Сцены эмулятора — отдельно: tests/levelmech/emu.sh barriers 2|5, ufo 7, shield 5 (и --negative).
cd "$(dirname "$0")/../.." || exit 2
rc=0
for g in coverage barriers flying safezone shield monkeys; do
  out=$(bash tests/levelmech/$g.sh 2>&1); r=$?
  echo "$out" | grep -E "^(RED|GREEN|GATE)"
  [ $r -eq 0 ] || rc=1
done
[ $rc -eq 0 ] && echo "ВСЕ ГЕЙТЫ МЕХАНИК: PASS" || echo "ВСЕ ГЕЙТЫ МЕХАНИК: FAIL"
exit $rc
