#!/bin/bash
# Сборка ботов на Маке (пункты Б0–Б5): тот же C-код логики, что EBOOT. tools/bots/build.sh [доп. флаги cc]
#   -DBW_BREAK_LOAD=1 — отрицательный контроль гейта save/load (загрузка без монет)
#   V_DIR=путь OUT_DIR=путь — собрать из другой копии viewer/ в другую папку (гейт Т1.4: откат исправления)
set -e; cd "$(dirname "$0")/../.."; O=${OUT_DIR:-build/bots}; mkdir -p "$O"
V=${V_DIR:-viewer}
. tools/bots/lib.sh; LIB="$BOTS_LIB"   # общий список исходников мира (tools/bots/lib.sh)
CC="cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I $V -I tools/bots $*"
# SUF=_broken tools/bots/build.sh -D...: собрать отрицательный контроль рядом, не затирая рабочие бинарники
for b in ${BINS:-game_headless nav missioner explorer chase longworld probe aocheck inspector}; do $CC tools/bots/$b.c $LIB -lm -o "$O/$b${SUF:-}"; echo "$O/$b${SUF:-}"; done
