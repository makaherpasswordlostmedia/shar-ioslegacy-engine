#!/bin/bash
# №953 приёмка (окно «Глюки», TEST60/61): дым машины (smoke1/2/3/3alph) — мягким смешиванием как в оригинале, без чёрных заливок по углам и трещин между клубами.
# Один тур-EBOOT, в сценарии flag smoke953 0 (прежнее, вырезка №731 — КРАСНЫЙ) и 1 (новое — ЗЕЛЁНЫЙ), одна и та же машина (L1, урон 0,35, мультик вкл), кадр без дыма как эталон. Последняя строка: PASS или FAIL.
#   tests/smoke953/accept60.sh      REUSE=1 — не пересобирать EBOOT и не гонять эмулятор, если уже есть
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH EMU_OWNER=${EMU_OWNER:-Glyuki} EMU_MINE=2 OUT=$W/run
mkdir -p run
if [ "${REUSE:-0}" != 1 ] || [ ! -f viewer/build_t60/EBOOT.PBP ]; then
  ( cd viewer && psp-cmake -S . -B build_t60 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1" >/dev/null 2>&1 && cmake --build build_t60 -j4 >run/build953.log 2>&1 ) || { echo "сборка не удалась (run/build953.log)"; echo FAIL; exit 2; }
fi
[ "${REUSE:-0}" = 1 ] && [ -f run/out_ab/ref.png ] || bash tools/emu_run.sh tests/smoke953/scenario.txt ab viewer/build_t60/EBOOT.PBP 600 >/dev/null 2>&1
[ -f run/out_ab/ref.png ] || { echo "прогон не дал кадров"; echo FAIL; exit 2; }
o=$(python3 tests/smoke953/check.py run/out_ab old); orc=$?; n=$(python3 tests/smoke953/check.py run/out_ab new); nrc=$?
echo "прежнее (вырезка): $(echo "$o" | head -1) -> $([ $orc != 0 ] && echo 'красный, как нужно' || echo 'ЗЕЛЁНЫЙ (красный не пойман)')"
echo "новое (мягкий дым): $(echo "$n" | head -1) -> $([ $nrc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
if [ $nrc = 0 ] && [ $orc != 0 ]; then echo PASS; else echo FAIL; fi
