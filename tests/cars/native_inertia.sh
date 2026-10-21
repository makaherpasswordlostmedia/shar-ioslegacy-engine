#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
inertia_out="${OUT_DIR:-build/cars-native-inertia}"
inertia_ram="${NATIVE_RAM:-build/codex-terminal/rob-rest/388/native-ee.bin}"
inertia_trace="${NATIVE_TRACE:-build/codex-terminal/rob-rest/388/attempt8/original-drop/trace.json}"
mkdir -p "$inertia_out"
.venv/bin/python tools/car_inertia_export.py --out "$inertia_out/profiles.h" --report "$inertia_out/profiles.json" > "$inertia_out/export.log"
cmp viewer/car_inertia.h "$inertia_out/profiles.h"
cc -std=c11 -O2 -I viewer tests/cars/native_inertia.c viewer/col.c -lm -o "$inertia_out/green"
"$inertia_out/green" > "$inertia_out/green.log"
.venv/bin/python tests/cars/native_inertia.py "$inertia_out/green.log" "$inertia_out/profiles.json" "$inertia_ram" "$inertia_trace"
cc -std=c11 -O2 -DCAR_NATIVE_PHYSICS_OLD=1 -I viewer tests/cars/native_inertia.c viewer/col.c -lm -o "$inertia_out/red"
"$inertia_out/red" > "$inertia_out/red.log"
if .venv/bin/python tests/cars/native_inertia.py "$inertia_out/red.log" "$inertia_out/profiles.json" "$inertia_ram" "$inertia_trace" > "$inertia_out/red-check.log" 2>&1; then
 echo 'FAIL old box inertia negative control not detected';exit 1
fi
echo 'PASS old box inertia negative control detected'
