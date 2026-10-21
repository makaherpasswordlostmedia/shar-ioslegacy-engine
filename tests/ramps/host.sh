#!/bin/bash
# Трамплины со стеклом Krusty: щель в коллизии не должна работать как край мира (tests/ramps/host.c)
#   tests/ramps/host.sh [level.shr] ; CAR_C=путь/к/car.c — прогнать на другой версии физики (отрицательный контроль)
set -eu
cd "$(dirname "$0")/../.."
out=build/ramps-host
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/ramps/host.c \
  "${CAR_C:-viewer/car.c}" viewer/col.c viewer/props.c viewer/stateprops.c viewer/coins.c -lm -o "$out"
"$out" "${1:-build/level.shr}"
