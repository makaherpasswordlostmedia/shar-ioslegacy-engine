#!/bin/bash
# RESET CAR выручает: tests/reset/host.sh [LEVEL]; CAR_C=старый car.c — сравнение
set -e; cd "$(dirname "$0")/../.."; mkdir -p build
cc -std=c11 -O2 -I viewer tests/reset/host.c "${CAR_C:-viewer/car.c}" "${COL_C:-viewer/col.c}" -lm -o build/reset-host
build/reset-host "${1:-build/level.shr}"
