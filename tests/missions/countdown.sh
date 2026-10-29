#!/bin/bash
# Отсчёт 3-2-1 этапа (отзыв Роба 28.09): во время отсчёта игрок стоит (газ/руль не проходят, ручник), на GO управление
# возвращается. Гонка sr1, газ и руль зажаты весь отсчёт. Красный: сборка -DGAME_MSN_FREEZE=0 (газ проходит) обязана упасть.
#   tests/missions/countdown.sh -> PASS/FAIL
cd "$(dirname "$0")/../.."
A="build/level.shr build/homer.shr build/missions/level01.msn"
BINS=cdfreeze tools/bots/build.sh >/dev/null || exit 1
BINS=cdfreeze SUF=_nofreeze tools/bots/build.sh -DGAME_MSN_FREEZE=0 >/dev/null || exit 1
echo "== газ проходит во время отсчёта (отрицательный контроль, обязан упасть):"; build/bots/cdfreeze_nofreeze $A; NEG=$?
echo "== как в оригинале:"; build/bots/cdfreeze $A; POS=$?
if [ $NEG != 0 ] && [ $POS = 0 ]; then echo PASS; else echo "FAIL (без заморозки: код $NEG, с заморозкой: код $POS)"; exit 1; fi
