#!/bin/bash
# №914 гейт: слоты костей пачек переставлены без изменения скиннинга (viewer/skin.c skinSlotOpt, SKIN_SLOTOPT_OLD)
#   tests/skinslot/gate.sh [DIR_С_CHR]   — PASS: расхождение <= 1e-4, загрузок матриц меньше; красный контроль: tests/skinslot/gate.sh red (кости переставлены, веса нет) -> FAIL
cd "$(dirname "$0")/../.."; D=${1:-$HOME/Downloads/shar-psp-integ/build/test56tour/PSP/GAME/SHARTEST15/chars}; F=""; [ "$1" = red ] && { F=-DSKIN_SLOTOPT_BREAK; D=$HOME/Downloads/shar-psp-integ/build/test56tour/PSP/GAME/SHARTEST15/chars; }
T=${TMPDIR:-/tmp}/ss914.$$; cc -std=c11 -O1 -DSKIN_HOST $F -I viewer tests/skinslot/check.c viewer/skin.c -lm -o $T || exit 2; $T "$D"; r=$?; rm -f $T; exit $r
