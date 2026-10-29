#!/bin/bash
# Actual carUpdate: valid high-drop landings do not trigger a delayed reset
# Legacy rule must fail; missing-ground recovery stays active in both builds
set -eu
cd "$(dirname "$0")/../.."
landing_out="${OUT_DIR:-build/cars-landing-timer}"
mkdir -p "$landing_out"
cc -std=c11 -O2 -Wall -Wno-unused-function -I viewer tests/cars/landing_timer.c viewer/car.c viewer/col.c -lm -o "$landing_out/green"
cc -std=c11 -O2 -Wall -Wno-unused-function -DCAR_LANDING_RESET_OLD=1 -I viewer tests/cars/landing_timer.c viewer/car.c viewer/col.c -lm -o "$landing_out/red"
"$landing_out/green" > "$landing_out/green.log"
if "$landing_out/red" > "$landing_out/red.log"; then
  echo 'FAIL legacy landing-reset rule was not detected'; exit 1
fi
if ! grep -Eq '^FAIL native tuning=[0-9]+ landing cases=[0-9]+ failures=[1-9][0-9]* void recovery=1$' "$landing_out/red.log"; then
  echo 'FAIL negative control did not complete its recovery check'; exit 1
fi
tail -1 "$landing_out/green.log"
tail -1 "$landing_out/red.log"
echo 'PASS old reset detected; invalid-state recovery retained'
