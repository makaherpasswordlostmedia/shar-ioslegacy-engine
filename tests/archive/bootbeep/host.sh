#!/bin/bash
# Проверка писка заставки на Маке: tests/bootbeep/host.sh [доп. флаги cc]; красное: -DBOOT_BEEP_HZ=440 | -DBOOT_BEEP_AMP=30000 | -DBOOT_BEEP_MS=900
set -e; cd "$(dirname "$0")/../.."
cc -std=c99 -O1 -Wall -I viewer "$@" tests/bootbeep/host.c -o build/bootbeep-host -lm && build/bootbeep-host
