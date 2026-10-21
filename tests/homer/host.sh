#!/bin/bash
# Native harness for Homer (viewer/homer.c) on the Mac: movement numbers, COL1 collision, car in/out, Ф3 episode.
#   tests/homer/host.sh [level.shr] [homer.shr]
set -e
cd "$(dirname "$0")/../.."
[ -f build/homer.shr ] || { source .venv/bin/activate; python tools/homer_export.py > /dev/null; }
T=${TMPDIR:-/tmp}/homer_host.$$
cc -std=c99 -O2 -Wall -Wno-unused-function -DSKIN_HOST $HOST_CFLAGS -I viewer tests/homer/host_homer.c viewer/homer.c viewer/skin.c \
   viewer/col.c viewer/car.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o "$T"
"$T" "${1:-build/level.shr}" "${2:-build/homer.shr}"; r=$?; rm -f "$T"; exit $r
