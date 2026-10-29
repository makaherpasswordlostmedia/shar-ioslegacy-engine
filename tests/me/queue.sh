#!/bin/bash
# Гейт очереди Media Engine без PSP и без данных игры (облако 05.10): 1) tests/me/chain.sh — все порядки шагов договора;
# 2) tests/me/queue_host.c — настоящие потоки «ME»/звук/частицы на общем коде meBoxSubmit: зелёный — звук не теряется и не считается
# дважды, на главном ≤ 2 %, при зависшем ME теряется ≤ 1 задание; КРАСНЫЙ -DME_CHAIN_OLD=1 (без очереди) — звук на главном > 8 %.
set -u; cd "$(dirname "$0")/../.."; mkdir -p build/me
bash tests/me/chain.sh | tail -1 | grep -q PASS && { echo "порядки шагов (chain.sh): PASS"; c=1; } || { echo "порядки шагов (chain.sh): FAIL"; c=0; }
CC="cc -std=c11 -O2 -Wall -pthread -I viewer"
$CC -DME_CHAIN_OLD=1 tests/me/queue_host.c -o build/me/queue_red || exit 2
build/me/queue_red > build/me/queue_red.txt; pm=$(sed -n 's/^RESULT_N main_pct=\([0-9.]*\).*/\1/p' build/me/queue_red.txt)
if awk -v p="$pm" 'BEGIN{exit !(p > 8)}'; then echo "красный (без очереди): звук на главном $pm % — пойман"; red=1; else echo "КРАСНЫЙ НЕ ПОЙМАН ($pm %)"; red=0; fi
$CC tests/me/queue_host.c -o build/me/queue || exit 2
build/me/queue | tee build/me/queue.txt | grep -v "^RESULT_N"; rc=${PIPESTATUS[0]}
[ $c -eq 1 ] && [ $red -eq 1 ] && [ $rc -eq 0 ] && { echo "PASS"; exit 0; }; echo "FAIL"; exit 1
