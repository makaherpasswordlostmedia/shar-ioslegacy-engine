#!/bin/bash
# Проверка звука включения заставки на Маке (правка 128): tests/bootsnd/host.sh [доп. флаги cc]
# красное: -DBOOT_SND_CLICK=0 | -DBOOT_SND_FAN_TAU=0 | -DBOOT_BEEP_LP=0.55f | -DBOOT_SND_CHUNK=1000
set -e; cd "$(dirname "$0")/../.."
cc -std=c99 -O1 -Wall -I viewer "$@" tests/bootsnd/host.c -o build/bootsnd-host -lm && build/bootsnd-host
