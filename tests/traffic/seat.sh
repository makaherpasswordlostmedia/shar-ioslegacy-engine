#!/bin/bash
# №666 гейт посадки в угнанную машину трафика: tests/traffic/seat.sh [traffic.shr]  (по умолчанию build/traffic.shr). Красный: -DTRF_SEAT_OLD=1 (CFLAGS_EXTRA) или пакет без блока сидений
set -e; cd "$(dirname "$0")/../.."
T=${TMPDIR:-/tmp}/trfseat.$$
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/traffic/seat.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c ${CFLAGS_EXTRA:-} -lm -o "$T"
set +e; "$T" "${1:-build/traffic.shr}"; r=$?; rm -f "$T"; exit $r
