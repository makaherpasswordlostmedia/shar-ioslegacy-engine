#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
out=build/traversal-host
cc -std=c99 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/traversal/host.c \
  viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c viewer/stateprops.c viewer/coins.c -lm -o "$out"
"$out" "${1:-build/level.shr}" "${2:-build/homer.shr}"
