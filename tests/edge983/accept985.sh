#!/bin/bash
# №985 приёмка: тротуар по умолчанию холодным серым (оттенок варианта Б №974) с ровным бумажным зерном. accept985.sh NEW_EBOOT [red]; нужен OVL с flat912.bin нового вида (tools/flat_list.py)
#   Мера: в окне тротуара (правая верхняя часть кадра) среднее (R − B): у тёплого тротуара TEST67 больше +15, у холодного серого меньше −5; пятнистость — разброс средних по блокам 16×16 окна не больше 3,5 единиц яркости (у старого шума с пятнами около 8).
#   «red» — красный контроль: «стало» = «было» (флаг 0) -> тротуар остаётся тёплым -> FAIL. Последняя строка PASS / FAIL
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/walkcold985_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; MODE=1; [ "${2:-}" = red ] && MODE=0
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
[ -n "${OVL:-}" ] || { echo "нужен OVL с flat912.bin нового вида"; echo FAIL; exit 1; }
mkdir -p $OUT; N=w985_$MODE; sed "s/MODE/$MODE/g" $D/scenario985.txt > $OUT/$N.txt; rm -rf $OUT/out_$N
$RUN $OUT/$N.txt $N "$EB" 300 >/dev/null 2>&1
python3 -I - "$OUT/out_$N" <<'PYEOF'
import sys
from PIL import Image
import numpy as np
d = sys.argv[1]
def win(f): return np.asarray(Image.open(f).convert('RGB'), float)[80:120, 260:380]
try: a, b = win(d + '/w_was.png'), win(d + '/w_new.png')
except OSError: print('нет кадров'); print('FAIL'); sys.exit(1)
rb = lambda x: float((x[:, :, 0] - x[:, :, 2]).mean())
ok_w, ok_c = rb(a) > 60, rb(a) - rb(b) > 50
print('  %s тёплый тротуар «было»: R−B = %.1f (нужно > 60)' % ('ok  ' if ok_w else 'FAIL', rb(a)))
print('  %s холодный серый «стало»: R−B = %.1f (нужно меньше, чем «было», на 50 и больше)' % ('ok  ' if ok_c else 'FAIL', rb(b)))
L = b @ [.299, .587, .114]; blk = L[:32, :112].reshape(2, 16, 7, 16).mean(axis=(1, 3)); sp = float(blk.std())
ok_s = sp <= 3.5
print('  %s пятнистость (разброс блоков 16×16): %.2f (нужно <= 3,5)' % ('ok  ' if ok_s else 'FAIL', sp))
good = ok_w and ok_c and ok_s
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
