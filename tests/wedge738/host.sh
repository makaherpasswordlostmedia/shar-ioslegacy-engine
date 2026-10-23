#!/bin/bash
# №738 зажатая машина (tests/wedge738/host.c). EXTRA=-DWEDGE738_OLD=1 — как было (красный)
set -eu
cd "$(dirname "$0")/../.."; mkdir -p build
cc -std=c11 -O2 -Wall -Wno-unused-function ${EXTRA:-} -I viewer tests/wedge738/host.c viewer/car.c viewer/col.c -lm -o build/wedge738-host
build/wedge738-host
