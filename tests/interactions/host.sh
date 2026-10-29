#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
out=${INTERACTION_TEST_OUT:-build/interactions-host}
mkdir -p "$out"
cc -std=c11 -O2 -Wall -Wextra -Wno-unused-function -Wno-missing-field-initializers -DSKIN_HOST -I viewer \
  tests/interactions/host.c viewer/props.c viewer/stateprops.c viewer/col.c viewer/car.c viewer/coins.c \
  viewer/homer.c viewer/skin.c -lm -o "$out/host"
"$out/host" "${1:-build/level_ep.shr}" "${2:-build/homer.shr}"
