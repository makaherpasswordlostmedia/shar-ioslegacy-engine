#!/bin/bash
# №949 приёмка: шум земли — один размер зерна в метрах на любой поверхности. accept60.sh NEW_EBOOT [red]
#   Мак строит noise949.bin для L6 (tools/noise949_list.py), сценарий снимает газон сверху с правилом и без него («flag noise949 0» — шум по родным UV, как TEST59).
#   Мера: энергия полосы 4–12 px (разность размытий Гаусса) на участке газона. С правилом зерно дробится до 5 м — энергия полосы выше.
#   PASS: энергия с правилом / без >= 1.2. «red» — красный контроль: оба снимка без правила -> отношение ~1 -> FAIL. Последняя строка PASS / FAIL
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/noise949_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; MODE=1; [ "${2:-}" = red ] && MODE=0
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
OV=$OUT/ovl949; mkdir -p $OV/l6 $OUT
( . $I/.venv/bin/activate; python $I/tools/noise949_list.py $SET/l6/level.shr $OV/l6/noise949.bin ) >/dev/null 2>&1
[ -f $OV/l6/noise949.bin ] || { echo "не построен noise949.bin"; echo FAIL; exit 1; }
N=nz949_$MODE; sed "s/MODE/$MODE/" $D/scenario.txt > $OUT/$N.txt
OVL=$OV SET=$SET $RUN $OUT/$N.txt $N "$EB" 500 >/dev/null 2>&1
python3 -I - "$OUT/out_$N" "$MODE" <<'PYEOF'
import sys, re
from PIL import Image, ImageFilter
import numpy as np
d, mode = sys.argv[1], sys.argv[2]
log = open(d + '/smoke.txt', errors='replace').read()
m = re.search(r'NOISE949 level=6 ok=(\d) [^\n]*pieces=(\d+)', log)
ok = bool(m and m.group(1) == '1' and int(m.group(2)) > 100)
print('  %s noise949.bin прочитан на L6: %s' % ('ok  ' if ok else 'FAIL', m.group(0) if m else 'строки NOISE949 нет'))
box = (150, 90, 400, 260)
def band(f):
    im = Image.open(f).convert('L').crop(box); b = lambda s: np.asarray(im.filter(ImageFilter.GaussianBlur(s)), float)
    return float((b(4) - b(12))[20:-20, 20:-20].std())
e_on, e_off = band(d + '/top_on.png'), band(d + '/top_off.png'); r = e_on / e_off
print('  энергия полосы 4–12 px: с правилом %.3f, без %.3f, отношение %.2f (нужно >= 1.20)' % (e_on, e_off, r))
good = ok and r >= 1.2
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
