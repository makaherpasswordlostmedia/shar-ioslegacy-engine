#!/bin/bash
# Build the real wardrobe controller as a host unit and check shipped disc contracts.
# tests/shop/wardrobe_levels.sh --export --gate
# tests/shop/wardrobe_levels.sh --data build/ship_stage --gate
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
mkdir -p build/wardrobe-levels
V=viewer; . tools/bots/lib.sh
cc -std=c11 -O2 -Wno-misleading-indentation -DSKIN_HOST -DWARDROBE_HOST \
  -I viewer -I tools/bots -I tests/shop tests/shop/wardrobe_levels_host.c \
  $BOTS_LIB -lm -o build/wardrobe_levels_host 2> build/wardrobe-levels/host-build.txt
.venv/bin/python -u tests/shop/wardrobe_levels.py "$@"
