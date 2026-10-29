#!/bin/bash
# Щитки m4 (П1, L1_ФИНИШ 30.09): этап delivery включает 9 щитков PP_powerbox1..9 (стейтпропы с тегом, s0 -> s1); два пинка □
# ломают щиток 3 (s1 -> s2 -> s3 OBJECT_DESTROYED) — цель миссии засчитана 1 из 9, остальные целы. Код логики общий с EBOOT
# (viewer/game_msn.c). Красный: та же проверка на сборке без связи щитков с миссией (-DGAME_MSN_BREAKABLES=0, как до 30.09)
# обязана упасть.   tests/missions/powerbox.sh -> PASS/FAIL
cd "$(dirname "$0")/../.."
A="build/level.shr build/homer.shr build/missions/level01.msn"
BINS=powerbox tools/bots/build.sh >/dev/null || exit 1
BINS=powerbox SUF=_nobreak tools/bots/build.sh -DGAME_MSN_BREAKABLES=0 >/dev/null || exit 1
echo "== без связи щитков с миссией (отрицательный контроль, обязан упасть):"; build/bots/powerbox_nobreak $A; NEG=$?
echo "== со связью:"; build/bots/powerbox $A; POS=$?
if [ $NEG != 0 ] && [ $POS = 0 ]; then echo PASS; else echo "FAIL (без связи: код $NEG, со связью: код $POS)"; exit 1; fi
