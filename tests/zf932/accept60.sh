#!/bin/bash
# Приёмка №932б (окно «Оптимизация»): ОДНА команда  tests/zf932/accept60.sh  — собирает новую (две области глубины) и прежнюю (-DZF932_OLD=1) сборки тура со смоуком,
# гоняет датчик мерцания flick на L3 и L5 (tests/zf932/flick_l3.txt, flick_l5.txt; tools/emu_run.sh, EMU_OWNER=Оптимизация), сверяет tests/zf932/gate.py; красный контроль: прежняя сборка против самой себя обязана упасть.
# Последняя строка PASS или FAIL.  NOBUILD=1 — сборки уже есть (viewer/build_a60_new, build_a60_old); OUT — папка прогонов
set -u -o pipefail
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"
export PATH="$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH"; export PSPDEV="$W/pspdev"; export PATH="$W/pspdev/bin:$PATH"
OUT="${OUT:-$W/build/accept60_zf932}"; mkdir -p "$OUT"; export EMU_OWNER="${EMU_OWNER:-Оптимизация}" EMU_MINE="${EMU_MINE:-2}"
B="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"; rc=0
bld() { (cd viewer && psp-cmake -S . -B build_a60_$1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$B $2" >/dev/null 2>&1 && cmake --build build_a60_$1 -j3 > "$OUT/build_$1.log" 2>&1) || { echo "СБОРКА $1 УПАЛА: $OUT/build_$1.log"; echo FAIL; exit 1; }; }
if [ "${NOBUILD:-0}" != 1 ]; then echo "== сборка"; bld new "" ; bld old "-DZF932_OLD=1"; fi
for v in new old; do [ -f viewer/build_a60_$v/EBOOT.PBP ] || { echo "нет EBOOT $v"; echo FAIL; exit 1; }; done
cmp -s viewer/build_a60_new/EBOOT.PBP viewer/build_a60_old/EBOOT.PBP && { echo "новая и прежняя сборки совпали: флаг не доехал"; echo FAIL; exit 1; }
echo "== прогоны датчика мерцания (L3 и L5, новая и прежняя)"
for v in new old; do for L in l3 l5; do OUT="$OUT/$v" tools/emu_run.sh tests/zf932/flick_$L.txt $L viewer/build_a60_$v/EBOOT.PBP 500 > "$OUT/run_${v}_$L.log" 2>&1 & done; wait; done
cat "$OUT"/run_*.log
S() { echo "$OUT/$1/out_$2/smoke.txt"; }
echo "== гейт: новая против прежней"
python3 tests/zf932/gate.py "$(S old l3)" "$(S old l5)" "$(S new l3)" "$(S new l5)" || rc=1
echo "== красный контроль: прежняя против прежней (обязан упасть)"
if python3 tests/zf932/gate.py "$(S old l3)" "$(S old l5)" "$(S old l3)" "$(S old l5)" | tail -4; then echo "красный НЕ упал"; rc=1; else echo "красный упал, как должен"; fi
[ $rc = 0 ] && echo PASS || echo FAIL; exit $rc
