#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
foliage_bin="${OUT_DIR:-build}/foliage-host"
mkdir -p "$(dirname "$foliage_bin")"
cc -O2 -std=c99 -Wall -I viewer tests/foliage/host.c "${CAR_C:-viewer/car.c}" "${COL_C:-viewer/col.c}" -lm -o "$foliage_bin"
"$foliage_bin" "${1:-build/level.shr}"
