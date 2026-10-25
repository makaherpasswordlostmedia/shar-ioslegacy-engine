#!/bin/bash
# №943 приёмка одной командой (окно msnhome, TEST60): «остаётся миссия "приехать домой"; выбранная миссия главнее стартовой цели».
#   tests/msnhome/accept60.sh            — собирает зелёный EBOOT и красный (-DMS_CURSOR_OLD=1 -DLVDEFER_OLD=1 -DMSN_SWITCH_OLD=1), гоняет в эмуляторе
#                                          два сценария на каждом (s1_levels: пауза -> MISSION SELECT -> ◄ ► -> ✕, два перехода уровней; s2_switch: смена миссий),
#                                          зелёный обязан пройти check.py, красный — упасть; снимки до/после -> $HOME/Downloads/shar-psp/build/t60/shots_msnhome/
#   ACC_SKIP_BUILD=1 — не пересобирать (EBOOT уже в $OUT/EBOOT_new.PBP и EBOOT_old.PBP).  Последняя строка: PASS или FAIL
set -u
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W=$(cd "$(dirname "$0")/../.." && pwd)
export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH
OUT=${OUT:-$W/build/msnhome60/accept}; mkdir -p "$OUT"; export EMU_OWNER=msnhome
SH=$HOME/Downloads/shar-psp/build/t60/shots_msnhome
FLAGS="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1"
cfg() { psp-cmake -S "$W/viewer" -B "$W/viewer/$1" -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$2" > "$OUT/cfg_$1.log" 2>&1 \
        && cmake --build "$W/viewer/$1" -j4 > "$OUT/build_$1.log" 2>&1; }
if [ "${ACC_SKIP_BUILD:-0}" != 1 ]; then
  echo "[1/4] сборка зелёного EBOOT"; cfg build_t60 "$FLAGS" || { echo "сборка зелёного не удалась ($OUT/build_build_t60.log)"; echo "FAIL"; exit 1; }
  echo "[2/4] сборка красного EBOOT (-DMS_CURSOR_OLD=1 -DLVDEFER_OLD=1 -DMSN_SWITCH_OLD=1)"
  cfg build_t60_red "$FLAGS -DMS_CURSOR_OLD=1 -DLVDEFER_OLD=1 -DMSN_SWITCH_OLD=1" || { echo "сборка красного не удалась"; echo "FAIL"; exit 1; }
  cp "$W/viewer/build_t60/EBOOT.PBP" "$OUT/EBOOT_new.PBP"; cp "$W/viewer/build_t60_red/EBOOT.PBP" "$OUT/EBOOT_old.PBP"
fi
echo "[3/4] эмулятор: 4 прогона (по 2 разом, общая очередь Мака)"
run() { OUT="$OUT" "$W/tools/emu_run.sh" "$W/tests/msnhome/$1.txt" "$2" "$OUT/$3" "$4" > "$OUT/$2.log" 2>&1; }
run s1_levels s1new EBOOT_new.PBP 700 & run s2_switch s2new EBOOT_new.PBP 400 & wait
run s1_levels s1old EBOOT_old.PBP 700 & run s2_switch s2old EBOOT_old.PBP 400 & wait
echo "[4/4] проверка"
bad=0
chk() { local want=$1 mode=$2 name=$3 r; python3 "$W/tests/msnhome/check.py" "$mode" "$OUT/out_$name/smoke.txt" > "$OUT/check_$name.txt" 2>&1; r=$?
  sed 's/^/    /' "$OUT/check_$name.txt"
  if [ "$want" = green ] && [ $r -ne 0 ]; then echo "  !! $name обязан пройти"; bad=1; fi
  if [ "$want" = red ] && [ $r -eq 0 ]; then echo "  !! $name (красный контроль) обязан упасть, а прошёл: гейт ничего не доказывает"; bad=1; fi; }
echo "-- зелёный (новый код)"; chk green levels s1new; chk green switch s2new
echo "-- красный (прежнее поведение: обязан упасть)"; chk red levels s1old; chk red switch s2old
mkdir -p "$SH/before" "$SH/after"
python3 - "$OUT" "$SH" <<'EOF'
import sys
from pathlib import Path
from PIL import Image
out, sh = Path(sys.argv[1]), Path(sys.argv[2])
for tag, name in (('after', 's1new'), ('before', 's1old')):
    for s in ('hop1_ms_level', 'hop1_arrive', 'hop2_ms_level', 'hop2_arrive', 'hop1_after4s'):
        p = out / ('out_%s' % name) / (s + '.bmp')
        if p.exists(): Image.open(p).convert('RGB').save(sh / tag / (s + '.png'))
EOF
echo "снимки до/после: $SH"
if [ $bad -eq 0 ]; then echo PASS; else echo FAIL; fi
