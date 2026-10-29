#!/bin/bash
# №465 гейт стоп-сигналов: tests/traffic/brakelight.sh [traffic.shr]  (по умолчанию build/traffic.shr; пакет без бликов — красный). Красный контроль: -DTRF_BRAKELIGHT_OLD=1 на пакете с бликами
set -e; cd "$(dirname "$0")/../.."
T=${TMPDIR:-/tmp}/brakelight.$$
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/traffic/brakelight.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c ${CFLAGS_EXTRA:-} -lm -o "$T"
set +e; "$T" "${1:-build/traffic.shr}"; r=$?; rm -f "$T"; exit $r
