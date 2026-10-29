#!/bin/bash
# Гейт пункта ДОБИВКИ 26: viewer/menu_access.h против записей PS2 (tests/menu/access_host.c). Зелёный — новый код; три красных —
# тот же хост с -DPAUSE_MS_DIM_OLD=1, -DPAUSE_SUB_START_OLD=1, -DBOOTH_ACCESS_OLD=1: каждый обязан уронить свою группу проверок
# (и только её). Эмуляторная часть того же поведения — tests/menu/access_emu.sh.
#   tests/menu/access.sh   -> код 0 = OK
set -u; cd "$(dirname "$0")/../.."
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cc -std=c99 -Wall -Werror -O1 -o "$T/new" tests/menu/access_host.c || { echo "FAIL: сборка"; exit 1; }
"$T/new" > "$T/new.txt"; RC=$?; cat "$T/new.txt"
[ $RC -eq 0 ] || { echo "FAIL: зелёный не прошёл"; exit 1; }
for v in PAUSE_MS_DIM_OLD:ms PAUSE_SUB_START_OLD:start BOOTH_ACCESS_OLD:booth; do
  f=${v%%:*}; g=${v##*:}
  cc -std=c99 -Wall -Werror -O1 -D$f=1 -o "$T/$f" tests/menu/access_host.c || { echo "FAIL: сборка $f"; exit 1; }
  "$T/$f" > "$T/$f.txt"; r=$?
  n=$(grep -c "^CHECK $g .* FAIL" "$T/$f.txt"); o=$(grep "^CHECK" "$T/$f.txt" | grep -v "^CHECK $g " | grep -c FAIL)
  if [ $r -ne 0 ] && [ "$n" -gt 0 ] && [ "$o" -eq 0 ]; then
    echo "красный $f пойман: $n проверок группы $g FAIL ($(grep "^CHECK $g .* FAIL" "$T/$f.txt" | awk '{print $3}' | paste -sd, -))"
  else echo "FAIL: красный $f не пойман (код $r, своих FAIL $n, чужих $o)"; cat "$T/$f.txt"; exit 1; fi
done
echo "OK: menu access (зелёный + 3 красных)"
