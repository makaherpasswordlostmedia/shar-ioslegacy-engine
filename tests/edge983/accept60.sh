#!/bin/bash
# №983 приёмка: кромка тротуара у дороги серо-фиолетовым слоем (edge983.bin) и контур тропинок (pathlines983.shr). accept60.sh NEW_EBOOT [red]; нужен OVL с edge983.bin, pathlines983.shr (tools/edge983_list.py) и flat912.bin нового вида
#   Сценарий: L1, камера у угла, «было» и «стало» подряд, оба флага 0 («было») и MODE («стало»). Проверки: движок прочитал слой (EDGE983 verts > 0, рисует треугольники: EDGE983SET on=1 drawn > 0);
#   картинка: в полосе тротуара у дороги изменилось >= 1000 точек (разница суммы каналов > 40) у угла. «red» — красный контроль: «стало» = «было» (флаги 0) -> 0 точек -> FAIL. Последняя строка PASS / FAIL
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/edge983_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; MODE=1; [ "${2:-}" = red ] && MODE=0
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
[ -n "${OVL:-}" ] || { echo "нужен OVL с edge983.bin и flat912.bin нового вида"; echo FAIL; exit 1; }
mkdir -p $OUT; N=e983_$MODE; sed "s/MODE/$MODE/g" $D/scenario.txt > $OUT/$N.txt; rm -rf $OUT/out_$N
$RUN $OUT/$N.txt $N "$EB" 300 >/dev/null 2>&1
python3 -I - "$OUT/out_$N" "$MODE" <<'PYEOF'
import sys, re
from PIL import Image
import numpy as np
d, mode = sys.argv[1], sys.argv[2]
try: log = open(d + '/smoke.txt', errors='replace').read()
except OSError: print('нет smoke.txt'); print('FAIL'); sys.exit(1)
e = re.findall(r'EDGE983 level=1 cells=(\d+) verts=(\d+) pathcells=(\d+) pathlines=(\d+)', log)
ok_load = bool(e and int(e[-1][1]) > 0)
print('  %s слой кромки прочитан: %s' % ('ok  ' if ok_load else 'FAIL', e[-1:]))
s = re.findall(r'EDGE983SET t=[\d.]+ on=(\d) cells=\d+ verts=\d+ drawn=(\d+)', log)
ok_draw = bool(s and s[-1][0] == '1' and int(s[-1][1]) > 0)
print('  %s слой кромки включён и рисует: %s' % ('ok  ' if ok_draw else 'FAIL', s[-1:]))
good = ok_load and ok_draw
for cam, y0, y1 in (('k', 75, 150),):
    try:
        a = np.asarray(Image.open('%s/%s_was.png' % (d, cam)).convert('RGB'), int)[y0:y1, 0:380]; b = np.asarray(Image.open('%s/%s_new.png' % (d, cam)).convert('RGB'), int)[y0:y1, 0:380]
        n = int((np.abs(a - b).sum(axis=2) > 40).sum())
    except OSError: n = 0
    ok = n >= 1000
    print('  %s камера %s: изменившихся точек у кромки %d (нужно >= 1000, красный контроль даёт ~300)' % ('ok  ' if ok else 'FAIL', cam, n)); good = good and ok
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
