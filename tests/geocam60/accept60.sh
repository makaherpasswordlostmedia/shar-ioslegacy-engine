#!/bin/bash
# TEST60, окно geocam: приёмка №933 (свет пропов) и №939 (цена камеры в езде) ОДНОЙ командой. Сама собирает пять EBOOT (новый, прежний -D*_OLD=1, два красных контроля), гоняет зелёные и красные гейты через tools/emu_run.sh,
# последней строкой печатает PASS или FAIL (PASS = все зелёные зелёные И все красные красные).
#   tests/geocam60/accept60.sh            полный (включая регрессию камеры: eyejump, garage922, ctrl916, ~18 прогонов)
#   SKIP_REG=1 tests/geocam60/accept60.sh без регрессии камеры (быстрее)
#   OUT=папка  рабочая папка (по умолчанию tests/geocam60/out); EMU_OWNER=имя (по умолчанию geocam)
H=$(cd "$(dirname "$0")" && pwd); W=$(cd $H/../.. && pwd); export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
export OUT=${OUT:-$H/out} EMU_OWNER=${EMU_OWNER:-geocam}; mkdir -p $OUT; rc=0; cd $W/viewer
BASE="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
bld() { psp-cmake -S . -B build_a60_$1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$BASE $2" >/dev/null && cmake --build build_a60_$1 -j3 >$OUT/build_$1.log 2>&1 && echo "сборка $1 готова" || { echo "СБОРКА $1 УПАЛА (см. $OUT/build_$1.log)"; return 1; }; }
echo "== сборка (5 EBOOT, параллельно)"
bld new "" & bld old "-DSLPROPS933_OLD=1 -DCAM_NFREUSE_OLD=1 -DCG_DIRTY_OLD=1 -DCG_PEND_OLD=1" & bld rednf "-DCAM_NFREUSE_RED=1" & bld redpend "-DCG_PEND_RED=1" & wait
for v in new old rednf redpend; do [ -f build_a60_$v/EBOOT.PBP ] || { echo "нет EBOOT $v"; echo FAIL; exit 1; }; done; cd $W
N=viewer/build_a60_new/EBOOT.PBP; O=viewer/build_a60_old/EBOOT.PBP
chk() { # имя команда ожидание(0 — PASS, 1 — FAIL)
  out=$("${@:3}" 2>&1); r=$?; echo "$out" | sed 's/^/    /'; if [ $r = $2 ]; then echo "  [$1] как и должно быть (код $r)"; else echo "  [$1] НЕ ТАК: ждали код $2, получили $r"; rc=1; fi; }
echo "== №933 свет пропов: зелёный (новый), красный (сборка -DSLPROPS933_OLD=1)"
export OUT=$H/out/g933g; chk "933 зелёный" 0 bash tests/glow933/gate.sh $N 2
export OUT=$H/out/g933r; chk "933 красный: прежняя сборка" 1 bash tests/glow933/gate.sh $O d
echo "== №939 камера в езде: зелёный (CAMF, выбор клетки, быстрый путь, цена), красные (CAM_NFREUSE_RED, CG_PEND_RED)"
export OUT=$H/out/camf; chk "939 зелёный" 0 bash tests/campro/camf924.sh $N
chk "939 красный: ближняя плоскость" 1 bash tests/campro/camf924.sh --red viewer/build_a60_rednf/EBOOT.PBP
chk "939 красный: список клеток" 1 bash tests/campro/camf924.sh --red viewer/build_a60_redpend/EBOOT.PBP
if [ -z "$SKIP_REG" ]; then echo "== регрессия камеры №916/№920/№922 (камера у машины и у стены, курс ходьбы)"
  export OUT=$H/out/reg; chk "eyejump №916б/в" 0 bash tests/eyejump/eyejump.sh $N; chk "garage922" 0 bash tests/garage922/garage922.sh $N; chk "ctrl916/920" 0 bash tests/ctrl916/ctrl916.sh $N; fi
[ $rc = 0 ] && echo PASS || echo FAIL; exit $rc
