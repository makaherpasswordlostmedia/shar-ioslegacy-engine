#!/bin/bash
# №955б приёмка (окно «Глюки», TEST60/61): колёса машины миссии/угнанной под игроком крутятся (у неё carVisUpdate не вызывался, угол качения стоял на нуле при любой скорости).
# Сценарий steal.txt: уровень 1, пешком к школьному автобусу трафика (flag trfspawn 2), угон △, езда 6 с (flag autostraight), строки OWNANG (flag carang) — угол качения и скорость.
# Новый движок — ЗЕЛЁНЫЙ (угол растёт вместе с ходом), прежний (-DFORCEDSPIN955_OLD=1) — КРАСНЫЙ (угол стоит). Последняя строка PASS или FAIL.
# Вращение рисуется для всех моделей трафика L1–L7 (31 модель, flag trfwheel: кадры с углом 0 и 1,1 рад различаются у каждой) — отдельная проверка, tests/wheel955/models_L*.txt
#   tests/wheel955/accept60.sh      REUSE=1 — не пересобирать
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
set -u
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH EMU_OWNER=${EMU_OWNER:-Glyuki} EMU_MINE=2 OUT=$W/run; mkdir -p run
BASEF="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
build() { [ "${REUSE:-0}" = 1 ] && [ -f "viewer/$1/EBOOT.PBP" ] && return 0
  ( cd viewer && psp-cmake -S . -B "$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASEF $2" >/dev/null 2>&1 && cmake --build "$1" -j4 >"../run/build955_$1.log" 2>&1 ); }
build build_t60 "" & build build_old955 "-DFORCEDSPIN955_OLD=1" & wait
for b in build_t60 build_old955; do [ -f viewer/$b/EBOOT.PBP ] || { echo "нет сборки $b"; echo FAIL; exit 2; }; done
bash tools/emu_run.sh tests/wheel955/steal.txt acc955n viewer/build_t60/EBOOT.PBP 500 >/dev/null 2>&1 &
bash tools/emu_run.sh tests/wheel955/steal.txt acc955o viewer/build_old955/EBOOT.PBP 500 >/dev/null 2>&1 &
wait
n=$(python3 tests/wheel955/check.py run/out_acc955n/smoke.txt); nrc=$?; o=$(python3 tests/wheel955/check.py run/out_acc955o/smoke.txt); orc=$?
echo "новое:   $(echo "$n" | head -1) -> $([ $nrc = 0 ] && echo зелёный || echo 'КРАСНЫЙ (плохо)')"
echo "прежнее: $(echo "$o" | head -1) -> $([ $orc != 0 ] && echo 'красный, как нужно' || echo 'ЗЕЛЁНЫЙ (красный не пойман)')"
if [ $nrc = 0 ] && [ $orc != 0 ]; then echo PASS; else echo FAIL; fi
