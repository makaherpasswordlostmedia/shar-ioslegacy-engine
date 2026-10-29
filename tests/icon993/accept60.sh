#!/bin/bash
# №993 приёмка одной командой (окно Глюки): «дом Симпсонов в углу стоит только там, где этап зовёт SetHUDIcon("simpsons"); вне задания дома нет».
#   tests/icon993/accept60.sh   — собирает зелёный EBOOT и красный (-DICON993_OLD=1), гоняет в эмуляторе три сценария на каждом:
#       sel_L2, sel_L3 (NEW GAME, затем смена миссий: пузырь задания внизу, угол по секундам), probe_L7m3 (L7 m3 «въехать в луч», как кадр f967_brief тура TEST69);
#       зелёный обязан пройти check.py ok, красный (прежний код) — check.py bad (дом в углу при чужом этапе)
#   ACC_SKIP_BUILD=1 — не пересобирать (EBOOT уже в $OUT/EBOOT_new.PBP и EBOOT_old.PBP).  Последняя строка: PASS или FAIL
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd)
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
OUT=${OUT:-$W/build/icon993/accept}; mkdir -p "$OUT"; export EMU_OWNER=Glyuki EMU_MINE=${EMU_MINE:-2}
export SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test70tour/PSP/GAME/SHARTEST15}
FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
cfg() { psp-cmake -S "$W/viewer" -B "$W/viewer/$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$2" > "$OUT/cfg_$1.log" 2>&1 \
        && cmake --build "$W/viewer/$1" -j4 > "$OUT/build_$1.log" 2>&1; }
if [ "${ACC_SKIP_BUILD:-0}" != 1 ]; then
  echo "[1/4] сборка зелёного EBOOT"; cfg build_t60 "$FLAGS" || { echo "сборка зелёного не удалась ($OUT/build_build_t60.log)"; echo FAIL; exit 1; }
  echo "[2/4] сборка красного EBOOT (-DICON993_OLD=1)"; cfg build_t60_red "$FLAGS -DICON993_OLD=1" || { echo "сборка красного не удалась"; echo FAIL; exit 1; }
  cp "$W/viewer/build_t60/EBOOT.PBP" "$OUT/EBOOT_new.PBP"; cp "$W/viewer/build_t60_red/EBOOT.PBP" "$OUT/EBOOT_old.PBP"
fi
echo "[3/4] эмулятор: 6 прогонов (по 2 разом)"
run() { OUT="$OUT" "$W/tools/emu_run.sh" "$W/tests/icon993/$1.txt" "$2" "$OUT/$3" 130 > "$OUT/$2.log" 2>&1; }
for s in sel_L2 sel_L3 probe_L7m3; do run $s ${s}_new EBOOT_new.PBP & run $s ${s}_old EBOOT_old.PBP & wait; done
echo "[4/4] проверка"
bad=0
for s in sel_L2 sel_L3 probe_L7m3; do
  echo "-- $s зелёный (новый код)"; python3 "$W/tests/icon993/check.py" ok "$OUT/out_${s}_new/smoke.txt" | sed 's/^/    /'; [ ${PIPESTATUS[0]} -eq 0 ] || { echo "  !! $s новый обязан пройти"; bad=1; }
  echo "-- $s красный (прежний код: обязан упасть)"; python3 "$W/tests/icon993/check.py" bad "$OUT/out_${s}_old/smoke.txt" | sed 's/^/    /'; [ ${PIPESTATUS[0]} -eq 0 ] || { echo "  !! $s красный контроль не упал: гейт ничего не доказывает"; bad=1; }
done
if [ $bad -eq 0 ]; then echo PASS; else echo FAIL; fi
