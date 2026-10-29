#!/bin/bash
# Машина на машине (tests/carstack/host.c). CAR_C=путь/car.c CAR_H_DIR=папка с car.h EXTRA=-DCARHIT2 — старая версия
set -eu
cd "$(dirname "$0")/../.."
out=build/carstack-host
cc -std=c11 -O2 -Wall -Wno-unused-function ${EXTRA:-} -I "${CAR_H_DIR:-viewer}" -I viewer tests/carstack/host.c \
  "${CAR_C:-viewer/car.c}" viewer/col.c -lm -o "$out"
"$out"
