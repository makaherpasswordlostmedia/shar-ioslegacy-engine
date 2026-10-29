#!/bin/bash
# Stage-4 test EBOOT (emulator only; NOT for /Volumes/PSP): homer.shr export, main.c + Homer patch, build, run dir.
#   Shots: PPSSPP_SHOTS=$PWD/build/homertest/smoke.txt PPSSPP_SHOTDIR=build/homer_shots tools/ppsspp_run.sh $PWD/build/homertest/EBOOT.PBP 150
#   tests/homer/build.sh  ->  build/homertest/{EBOOT.PBP, homer.shr, level.shr -> ../level.shr, fx.shr -> ../fx.shr}
set -e
cd "$(dirname "$0")/../.."
source .venv/bin/activate
[ build/homer.shr -nt tools/homer_export.py ] || python tools/homer_export.py > /dev/null
mkdir -p tests/homer/build && python tests/homer/patch_main.py --out tests/homer/build/game.c
export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:$PATH
psp-cmake -S tests/homer -B tests/homer/build > /dev/null
cmake --build tests/homer/build 2>&1 | grep -E "error|warning: unused|homer" || true
D=build/homertest; mkdir -p $D
cp tests/homer/build/EBOOT.PBP build/homer.shr $D/ && grep -v '^#' tests/homer/scenario.txt > $D/scenario.txt
ln -sf ../level.shr $D/level.shr; ln -sf ../fx.shr $D/fx.shr
ls -la $D/EBOOT.PBP $D/homer.shr
