#!/bin/bash
# Гейт очереди ME (облако 05.10): tests/me/chain_host.c — все порядки шагов ME и главного. Красный -DCHAIN_NAIVE=1 обязан упасть.
set -u; cd "$(dirname "$0")/../.."; mkdir -p build/me
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -I viewer"
$CC -DCHAIN_NAIVE=1 tests/me/chain_host.c -o build/me/chain_red || exit 2
if build/me/chain_red > build/me/chain_red.txt; then echo "КРАСНЫЙ НЕ ПОЙМАН"; red=0; else echo "красный (наивная очередь): $(tail -1 build/me/chain_red.txt)"; red=1; fi
$CC tests/me/chain_host.c -o build/me/chain || exit 2
build/me/chain; rc=$?
[ $red -eq 1 ] && [ $rc -eq 0 ] && { echo "PASS"; exit 0; }; echo FAIL; exit 1
