#!/bin/bash
# Горбы-капсулы (тупик m0): tests/humps/host.sh [LEVEL] ; CAR_C=/путь/к/старому/car.c COL_C=... — сравнение со старым кодом
# красные правки 200 (остаток сверки): HUMPS_CFLAGS=-DFENCE_BEYOND_FRONT=1 (E падает), HUMPS_CFLAGS=-DHUMP_NO_KEEP=1 (G падает)
set -e; cd "$(dirname "$0")/../.."; mkdir -p build
cc -std=c11 -O2 ${HUMPS_CFLAGS:-} -I viewer tests/humps/host.c "${CAR_C:-viewer/car.c}" "${COL_C:-viewer/col.c}" -lm -o build/humps-host
build/humps-host "${1:-build/level.shr}"
