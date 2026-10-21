#!/bin/bash
# Хост-сверка отсечения города на ME (бит в бит) на всех уровнях пакета + красный контроль. Использование: tests/citycull/run.sh ПАПКА_ПАКЕТА
D=${1:?папка пакета (level.shr, l2..l7)}; cd "$(dirname "$0")/../.."; mkdir -p build
cc -O2 -std=gnu99 -ffp-contract=off -I viewer tests/citycull/host.c -lm -o build/citycull_host || exit 2
cc -O2 -std=gnu99 -ffp-contract=off -DNEG -I viewer tests/citycull/host.c -lm -o build/citycull_neg || exit 2
L=("$D/level.shr"); for n in 2 3 4 5 6 7; do [ -f "$D/l$n/level.shr" ] && L+=("$D/l$n/level.shr"); done
build/citycull_host "${L[@]}" | tail -1; CC_SYN=1 build/citycull_host "${L[@]}" | tail -1
if CC_SYN=1 build/citycull_neg "${L[@]}" >/dev/null; then echo "КРАСНЫЙ КОНТРОЛЬ НЕ СРАБОТАЛ"; exit 1; else echo "красный контроль: расхождение поймано (ожидалось)"; fi
