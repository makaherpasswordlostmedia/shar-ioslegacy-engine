#!/bin/bash
# Гейт разбора L3/L5, монеты по сетке (viewer/coins.c): состояние шага то же, что у прежнего полного обхода. Мак, только числа.
#   красные подброски: -DCOINGRID_BREAK_NEAR (радиус шага 1 м вместо 90 (клетки сетки 32 м: монеты у границы клетки не доберутся): далёкие монеты мира у игрока не успевают собраться — хеши расходятся), -DCOINGRID_BREAK_POOL (пул обходится, только когда poolActive не обновлён — выпавшие замирают)
#   зелёный: хеши на 6000 кадров ходьбы, езды и стоянки совпадают с прежним кодом
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"; T="${TMPDIR:-/tmp}/c913.$$"; mkdir -p "$T"
b() { local n=$1; shift; cc -O2 -std=c11 -I viewer "$@" tests/coins913/host.c viewer/coins.c -lm -o "$T/$n" || { echo "FAIL: сборка $n"; exit 1; }; "$T/$n" 6000 > "$T/$n.txt"; }
b old -DCOINGRID_OLD=1; b new; b red1 -DCOIN_NEAR_R_TEST=1.f; b red2 -DCOIN_POOL_BREAK=1
d() { diff -q "$T/old.txt" "$T/$1.txt" >/dev/null && echo 0 || echo $(diff "$T/old.txt" "$T/$1.txt" | grep -c '^<'); }
r1=$(d red1); r2=$(d red2); g=$(d new)
[ "$r1" != 0 ] || { echo "FAIL: красная подброска red1 (радиус 1 м) не расходится — проверка слепая"; exit 1; }
[ "$r2" != 0 ] || { echo "FAIL: красная подброска red2 (пул не обходится) не расходится — проверка слепая"; exit 1; }
echo "красные как надо: радиус 1 м — расхождений $r1 кадров; пул не обходится — $r2"
[ "$g" = 0 ] || { echo "FAIL: расхождений на новом коде: $g"; exit 1; }
echo "зелёный: 6000 кадров, хеши те же"; echo PASS
