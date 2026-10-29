#!/bin/bash
# Проверка анимации логотипа и хода заставки (пункт Л) на Маке: tests/bootlogo/host.sh [доп. флаги cc]
# Красное: -DBOOTANIM_GLYPHS='{0x054,0x092,0x111,0x1FF}' (толстый ■) или -DBOOTANIM_GOFS=0 (символы касаются знака)
set -e; cd "$(dirname "$0")/../.."
cc -std=c99 -O1 -Wall -I viewer "$@" tests/bootlogo/host.c -o build/bootlogo-host && build/bootlogo-host
