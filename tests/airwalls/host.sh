#!/bin/bash
# Правка 164 (Роб 01.10): невидимые стены в полёте с трамплина — повтор прыжка физикой порта (tests/airwalls/host.c).
#   tests/airwalls/host.sh scan X Z HEADING_DEG [--lat a:b:s] [--dh a:b:s] [--kmh a:b:s] [--secs S] [-v]
#   LEVEL=путь/к/level.shr — другой уровень (по умолчанию build/level.shr)
set -u
cd "$(dirname "$0")/../.."
out=build/tmp/airwalls-host; mkdir -p build/tmp
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/airwalls/host.c viewer/car.c viewer/col.c \
  viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o "$out" || exit 2
"$out" "${LEVEL:-build/level.shr}" "$@"
