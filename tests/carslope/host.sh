#!/bin/bash
# №879 удар машина-машина на склоне (tests/carslope/host.c). EXTRA=-DCARSLOPE879_OLD=1 — прежняя проверка высоты (красный контроль)
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build; out=build/carslope-host
cc -std=c11 -O2 -Wall -Wno-unused-function ${EXTRA:-} -I viewer tests/carslope/host.c viewer/car.c viewer/col.c -lm -o "$out"
"$out"
