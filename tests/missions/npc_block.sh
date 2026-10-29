#!/bin/bash
# Твёрдые персонажи миссий (отзыв Роба 28.09): Гомер идёт прямо на Мардж с четырёх сторон — обязан остановиться/обойти, не
# пройти насквозь; Мардж по маршруту не проходит сквозь Гомера. Код логики общий с EBOOT (viewer/game_msn.c).
# Красный: та же проверка на сборке без столкновений (-DGAME_NPC_SOLID=0) обязана упасть.   tests/missions/npc_block.sh -> PASS/FAIL
cd "$(dirname "$0")/../.."
# В85 (09.10): Мардж m0 — собеседник talkto, у неё правило остановки в 1.572 м (game_msn.h GAME_NPC_TALK_STOP); оно не даёт ей
# подойти к Гомеру и прячет отсутствие столкновений (строка «Мардж идёт на Гомера» без столкновений давала 1.580 -> ok). Здесь
# проверяется столкновение, поэтому обе сборки — без правила остановки (-DGAME_NPC_TALK_STOP_OLD=1); само правило проверяет
# tests/missions/marge_v85.sh. Каждая строка B обязана покраснеть без столкновений, не только итог.
A="build/level.shr build/homer.shr build/missions/level01.msn"
BINS=npcblock SUF=_solid tools/bots/build.sh -DGAME_NPC_TALK_STOP_OLD=1 >/dev/null || exit 1
BINS=npcblock SUF=_nosolid tools/bots/build.sh -DGAME_NPC_SOLID=0 -DGAME_NPC_TALK_STOP_OLD=1 >/dev/null || exit 1
echo "== без столкновений (отрицательный контроль, обязан упасть):"; NOUT=$(build/bots/npcblock_nosolid $A); NEG=$?; echo "$NOUT"
echo "== со столкновениями:"; build/bots/npcblock_solid $A; POS=$?
NB=$(printf '%s\n' "$NOUT" | grep -c '^B .*-> FAIL$'); NL=$(printf '%s\n' "$NOUT" | grep -c '^B ')
if [ $NEG != 0 ] && [ "$NB" = "$NL" ] && [ "$NL" -ge 5 ] && [ $POS = 0 ]; then echo PASS
else echo "FAIL (без столкновений: код $NEG, красных строк $NB из $NL; со столкновениями: код $POS)"; exit 1; fi
