#!/bin/bash
# №980 приёмка (окно «Глюки», основа test67): смена уровня закрывает будку, лавку, гардероб, паузу и снимает цель прошлого уровня (levelResetUi980, viewer/main_levels.h).
# Сценарий matrix.txt: будка L1 -> L2, будка L2 -> L3, пауза L3 -> L4, активная цель L4 -> L5; после каждой смены строка LVSTATE (check.py). Тур TEST67 (набор test67tour).
# Новый движок — ЗЕЛЁНЫЙ (после смены всё закрыто), прежний (-DLVRESET980_OLD=1) — КРАСНЫЙ (будка остаётся: phone=1 после смены). Последняя строка PASS или FAIL.
#   tests/lvreset980/accept60.sh      REUSE=1 — не пересобирать
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH EMU_OWNER=${EMU_OWNER:-Glyuki} EMU_MINE=2 OUT=$W/run; mkdir -p run
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test67tour/PSP/GAME/SHARTEST15}
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
build() { [ "${REUSE:-0}" = 1 ] && [ -f "viewer/$1/EBOOT.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 && cmake --build "$1" -j4 >"../run/build980_$1.log" 2>&1 ); }
build build_t60 "" & build build_old980 "-DLVRESET980_OLD=1" & wait
for b in build_t60 build_old980; do [ -f viewer/$b/EBOOT.PBP ] || { echo "нет сборки $b"; echo FAIL; exit 2; }; done
bash tools/emu_run.sh tests/lvreset980/matrix.txt a980n viewer/build_t60/EBOOT.PBP 500 >/dev/null 2>&1 &
bash tools/emu_run.sh tests/lvreset980/matrix.txt a980o viewer/build_old980/EBOOT.PBP 500 >/dev/null 2>&1 &
wait
n=$(python3 tests/lvreset980/check.py run/out_a980n/smoke.txt); nrc=$?; o=$(python3 tests/lvreset980/check.py run/out_a980o/smoke.txt); orc=$?
echo "новое:   $n -> $([ $nrc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
echo "прежнее: $o -> $([ $orc != 0 ] && echo 'красный, как нужно' || echo 'ЗЕЛЁНЫЙ (красный не пойман)')"
if [ $nrc = 0 ] && [ $orc != 0 ]; then echo PASS; else echo FAIL; fi
