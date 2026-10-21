#!/bin/bash
# №432 actual ramp flight; --old compiles the requested true negative control.
set -eu
cd "$(dirname "$0")/../.."
LEVEL=${1:-build/level.shr}; MODE=${2:-new}
FLAGS=(); [ "$MODE" != old ] || FLAGS=(-DDEATH_R6_RAMP_EXEMPT_OLD=1)
mkdir -p build/gates/ramp432
V=viewer; . tools/bots/lib.sh
cc -std=c11 -O2 -Wall -Wno-unused-function -Wno-misleading-indentation -DSKIN_HOST -I viewer -I tools/bots ${FLAGS[@]+"${FLAGS[@]}"} tests/death/ramp_host.c $BOTS_LIB -lm -o "build/gates/ramp432/$MODE"
"build/gates/ramp432/$MODE" "$LEVEL" "$(dirname "$LEVEL")/homer.shr"
