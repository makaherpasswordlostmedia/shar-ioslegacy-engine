#!/bin/bash
# ДОБИВКА 18 (правки 349/339, [PS2] В86/В87): зоны смерти и тупик L1 R6 — хост-гейт tests/death/r6_host.c на мире ботов.
#   tests/death/r6.sh [foot|deadend|sweep|all] [флаги cc] [-- LEVEL]   -> PASS / FAIL (LEVEL по умолчанию build/level.shr; рядом
#   build/homer.shr, traffic.shr). foot — В86 пешком (готово); deadend — В87 тупик, ИСХОД за окно PS2 (открыто: красный и на новом
#   коде); sweep — рецепт замера тупика (счёт «стоит» по линиям заезда и вводу); all (по умолчанию) — foot + deadend.
# Красный контроль — тот же гейт с прежним поведением обязан упасть:
#   tests/death/r6.sh foot -DDEATH_FOOT_OLD=1   (F1/F2: курс Гомера прежний, камера за спиной)
#   tests/death/r6.sh deadend -DDEADEND_OLD=1   (D1–D3: машина стоит в тупике)
set -u
cd "$(dirname "$0")/../.."
FLAGS=(); LEVEL=build/level.shr; PART=all
while [ $# -gt 0 ]; do case "$1" in --) shift; LEVEL=${1:-$LEVEL}; shift || true;; foot|deadend|sweep|all) PART=$1; shift;; *) FLAGS+=("$1"); shift;; esac; done
O=build/tmp/death; mkdir -p "$O"
V=viewer; . tools/bots/lib.sh
TAG=$(printf '%s' "${FLAGS[*]:-new}" | tr -c 'A-Za-z0-9' '_')
BIN=$O/r6_host_$TAG
cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I viewer -I tools/bots ${FLAGS[@]+"${FLAGS[@]}"} \
  tests/death/r6_host.c $BOTS_LIB -lm -o "$BIN" || { echo "сборка: FAIL"; exit 1; }
HOM=$(dirname "$LEVEL")/homer.shr; [ -f "$HOM" ] || HOM=build/homer.shr
echo "r6 [$PART]: ${FLAGS[*]:-новый код} · $LEVEL"
"$BIN" "$LEVEL" "$HOM" "$PART"
