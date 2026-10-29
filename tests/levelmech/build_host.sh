#!/bin/bash
# Сборка хост-проверки механик уровней (tests/levelmech/lvmech.c) из общего списка «игры без экрана» (tools/bots/lib.sh).
#   tests/levelmech/build_host.sh [доп. флаги cc]   ->  build/levelmech/lvmech${SUF}
#   -DSP_BILL_PVIS_ON=0 SUF=_nopvis — отрицательный контроль: огни барьеров не мигают
set -e; cd "$(dirname "$0")/../.."; O=build/levelmech; mkdir -p "$O"
V=${V_DIR:-viewer}
. tools/bots/lib.sh
cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I "$V" -I tools/bots "$@" \
  tests/levelmech/lvmech.c $BOTS_LIB -lm -o "$O/lvmech${SUF:-}"
echo "$O/lvmech${SUF:-}"
