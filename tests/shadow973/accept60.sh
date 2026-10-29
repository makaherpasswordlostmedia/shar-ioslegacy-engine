#!/bin/bash
# №973 приёмка (окно «Глюки», основа test66): тень своей машины (a) не уходит под опору при езде по холмам L4 (машина Мардж, автопилот flag drive) и (b) форма чистая и симметричная (L5 Апу: силуэт №811 с «огрызком» убран).
# Замер — строки SHADOW973 в smoke.txt (viewer/spritelight.h): кадры, где вершина тени ниже опоры коллизии (colGround под вершиной); несимметрия контура (расстояние до ближайшей зеркальной вершины).
# Новый движок — ЗЕЛЁНЫЙ (ниже опоры не больше 1 % кадров; несимметрия до 5 см), прежний (-DSHADOW973_OLD=1) — КРАСНЫЙ. Последняя строка PASS или FAIL.
#   tests/shadow973/accept60.sh      REUSE=1 — не пересобирать
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH EMU_OWNER=${EMU_OWNER:-Glyuki} EMU_MINE=2 OUT=$W/run; mkdir -p run
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test66tour/PSP/GAME/SHARTEST15}
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
build() { [ "${REUSE:-0}" = 1 ] && [ -f "viewer/$1/EBOOT.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 && cmake --build "$1" -j4 >"../run/build973_$1.log" 2>&1 ); }
build build_t60 "" & build build_old973 "-DSHADOW973_OLD=1" & wait
for b in build_t60 build_old973; do [ -f viewer/$b/EBOOT.PBP ] || { echo "нет сборки $b"; echo FAIL; exit 2; }; done
run2() { bash tools/emu_run.sh "$1" "$2" "$3" 400 >/dev/null 2>&1 & bash tools/emu_run.sh "$1" "$4" "$5" 400 >/dev/null 2>&1 & wait; }
run2 tests/shadow973/drive_L4.txt a973dn viewer/build_t60/EBOOT.PBP a973do viewer/build_old973/EBOOT.PBP
run2 tests/shadow973/still_L5.txt a973sn viewer/build_t60/EBOOT.PBP a973so viewer/build_old973/EBOOT.PBP
dn=$(python3 tests/shadow973/check.py drive run/out_a973dn/smoke.txt S_L4_drive); dnrc=$?
do=$(python3 tests/shadow973/check.py drive run/out_a973do/smoke.txt S_L4_drive); dorc=$?
sn=$(python3 tests/shadow973/check.py shape run/out_a973sn/smoke.txt); snrc=$?
so=$(python3 tests/shadow973/check.py shape run/out_a973so/smoke.txt); sorc=$?
echo "новое   езда L4: $dn -> $([ $dnrc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
echo "прежнее езда L4: $do -> $([ $dorc = 1 ] && echo 'красный, как нужно' || echo 'ЗЕЛЁНЫЙ (красный не пойман)')"
echo "новое   форма L5: $sn -> $([ $snrc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
echo "прежнее форма L5: $so -> $([ $sorc = 1 ] && echo 'красный, как нужно' || echo 'ЗЕЛЁНЫЙ (красный не пойман)')"
if [ $dnrc = 0 ] && [ $dorc = 1 ] && [ $snrc = 0 ] && [ $sorc = 1 ]; then echo PASS; else echo FAIL; fi
