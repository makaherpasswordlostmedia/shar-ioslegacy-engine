#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
suspension_out="${OUT_DIR:-build/cars-suspension}"
mkdir -p "$suspension_out"
.venv/bin/python tools/car_inertia_export.py --out "$suspension_out/profiles.h" --report "$suspension_out/profiles.json" > "$suspension_out/export.log"
cmp viewer/car_inertia.h "$suspension_out/profiles.h"
cc -std=c11 -O2 -I viewer tests/cars/suspension.c viewer/col.c -lm -o "$suspension_out/green"
"$suspension_out/green" > "$suspension_out/green.log"
.venv/bin/python tests/cars/suspension.py "$suspension_out/green.log" "$suspension_out/profiles.json"
cc -std=c11 -O2 -DSUSPENSION_EXPLICIT_CONTROL -I viewer tests/cars/suspension.c viewer/col.c -lm -o "$suspension_out/red"
"$suspension_out/red" > "$suspension_out/red.log"
if .venv/bin/python tests/cars/suspension.py "$suspension_out/red.log" "$suspension_out/profiles.json" > "$suspension_out/red-check.log" 2>&1; then
  echo 'FAIL explicit damping negative control was not detected';exit 1
fi
echo 'PASS explicit damping negative control detected'
