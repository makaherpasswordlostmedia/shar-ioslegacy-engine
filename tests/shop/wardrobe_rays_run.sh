#!/bin/bash
# wardrobe_rays_run.sh NAME SRC [flags] : безголовый прогон сценария гардероба -> build/rays/out_NAME
cd ~/Downloads/shar-psp-rays703
N=$1; S=$2; F=${3:-}; SC=${SC:-$PWD/build/rays/wr.txt}
L=$(SMOKE_HEADLESS=1 SHIP_LEVELS="" SMOKE_SCN=$SC SMOKE_HOME=$PWD/build/rays/home_$N SMOKE_MAXT=200 SMOKE_FLAGS="$F" tools/smoke.sh build/rays/$S 2>&1)
R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
rm -rf build/rays/out_$N; mv "$R" build/rays/out_$N; echo "$N -> out_$N"; echo "$L" | tail -4 | head -3
