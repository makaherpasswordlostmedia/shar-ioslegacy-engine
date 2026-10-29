#!/bin/bash
# сборка тура №984 камера: mk.sh ИМЯ "ДОП_ФЛАГИ"  (viewer/build_cr_ИМЯ), движок с -DZF932_OLD=1 как в TEST68
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W"; mkdir -p build/c984
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
F="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
( cd viewer && psp-cmake -S . -B build_cr_$1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$F $2" > "$W/build/c984/cfg_$1.log" 2>&1 && cmake --build build_cr_$1 -j4 > "$W/build/c984/b_$1.log" 2>&1 )
ls viewer/build_cr_$1/EBOOT.PBP
