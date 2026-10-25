#!/bin/bash
# №903 гейт: деревья всех 7 уровней сбиваются по стволу. Проезд мимо (зазор 1 м между бортом и стволом) настоящим car.c/props.c/col.c
# по данным набора; сумма «задето мимо» по всем деревьям: новое ≤ 1/4 прежнего, у дуба L1 (тип 8, F9-1 и аллея E8-9) — 0 (прежнее 8 из 12)
# Красный контроль — та же сборка с -DPROP_TRUNK_SLICE_OLD=1. Набор: SET (по умолчанию тур TEST52)
cd "$(dirname "$0")/../.."
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test52tour/PSP/GAME/SHARTEST15}; O=build/tests/props903; mkdir -p $O
for v in 0 1; do clang -std=c11 -O2 -DSKIN_HOST -DPROP_TRUNK_SLICE_OLD=$v -I viewer tests/props903/host.c viewer/col.c viewer/props.c viewer/stateprops.c viewer/car.c viewer/coins.c -lm -o $O/h$v || exit 2; done
tot() { local s=0; for L in 1 2 3 4 5 6 7; do f=$SET/level.shr; [ $L -gt 1 ] && f=$SET/l$L/level.shr; n=$($O/h$1 $f 1.0 | grep '^тип' | sed 's/.*задето \([0-9]*\) из.*/\1/' | paste -sd+ - | bc); s=$((s + n)); done; echo $s; }
N=$(tot 0); P=$(tot 1); oak=$($O/h0 $SET/level.shr 1.0 | grep '^тип  8 ' | sed 's/.*задето \([0-9]*\) из.*/\1/'); oakOld=$($O/h1 $SET/level.shr 1.0 | grep '^тип  8 ' | sed 's/.*задето \([0-9]*\) из.*/\1/')
echo "задето мимо, все уровни: новое $N, прежнее $P; дуб L1 (тип 8): новое $oak, прежнее $oakOld"
[ "$oakOld" -gt 0 ] || { echo "КРАСНЫЙ КОНТРОЛЬ НЕ ПАДАЕТ — гейт ничего не доказывает"; exit 3; }
[ "$oak" = 0 ] && [ $((N * 4)) -le "$P" ] && echo PASS || { echo FAIL; exit 1; }
