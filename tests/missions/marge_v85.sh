#!/bin/bash
# В85 (ДОБИВКА 21): Мардж на старте m0 стоит на расстоянии PS2 (1.473..1.572 м), Cancel разговора возвращает обоих на места до
# разговора (правило порта), повторное △ раньше 26 кадров PAL отклоняется; D — места после Cancel против PS2 (открыто). Игра без экрана (tests/missions/marge_v85_host.c), код логики общий с
# EBOOT. Красный контроль: та же проверка обязана упасть на прежнем поведении —
#   -DGAME_NPC_TALK_STOP_OLD=1 (часть A) и -DGAME_TALK_CANCEL_OLD=1 (части B, C).   tests/missions/marge_v85.sh -> PASS/FAIL
set -u
cd "$(dirname "$0")/../.."
DATA=${DATA:-build}
[ -f "$DATA/level.shr" ] || DATA="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/build"   # копия git worktree: данные основного дерева (чтение)
A="$DATA/level.shr $DATA/homer.shr $DATA/missions/level01.msn"
O=build/marge_v85; mkdir -p "$O"
V=viewer; . tools/bots/lib.sh
CC="cc -std=c11 -O2 -DSKIN_HOST -I viewer -I tools/bots"
$CC tests/missions/marge_v85_host.c $BOTS_LIB -lm -o "$O/new" || exit 1
$CC -DGAME_NPC_TALK_STOP_OLD=1 tests/missions/marge_v85_host.c $BOTS_LIB -lm -o "$O/stop_old" || exit 1
$CC -DGAME_TALK_CANCEL_OLD=1 tests/missions/marge_v85_host.c $BOTS_LIB -lm -o "$O/cancel_old" || exit 1
echo "== прежняя остановка (GAME_NPC_TALK_STOP_OLD=1, обязан упасть):"; "$O/stop_old" $A A; R1=$?
echo "== прежний Cancel (GAME_TALK_CANCEL_OLD=1, обязан упасть):"; "$O/cancel_old" $A BC; R2=$?
echo "== новый код:"; "$O/new" $A; G=$?
echo "== новый код, D: места после Cancel против PS2 (открытое расхождение по Мардж):"; "$O/new" $A D; D=$?
if ! { [ $R1 = 1 ] && [ $R2 = 1 ] && [ $G = 0 ]; }; then echo "FAIL (stop_old $R1, cancel_old $R2, новый $G)"; exit 1; fi
# A/B/C зелёные, красные контроли красные. D — абсолютные места PS2 после Cancel: пока Мардж не там, гейт красный (код 3, ЧАСТИЧНО)
if [ $D = 0 ]; then echo PASS; else echo "ЧАСТИЧНО: A/B/C PASS, D FAIL — места после Cancel не как у PS2 (код $D)"; exit 3; fi
