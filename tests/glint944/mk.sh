#!/bin/bash
# mk.sh ПАПКА [доп. флаги C]
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; W="$(cd "$(dirname "$0")/../.." && pwd)"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
export SDKROOT=${SDKROOT:-/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk}
mkdir -p $W/build/t60g944
cd $W/viewer && psp-cmake -S . -B $1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 $2" > $W/build/t60g944/cfg_$(basename $1).log 2>&1 && cmake --build $1 -j4 > $W/build/t60g944/build_$(basename $1).log 2>&1
grep -E " error" $W/build/t60g944/build_$(basename $1).log | head; tail -1 $W/build/t60g944/build_$(basename $1).log
