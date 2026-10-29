#!/bin/bash
# №956 приёмка: машины NPC — серая краска кузова в тон палитры Симпсонов (tools/car_flat.py recolor956). accept60.sh NEW_EBOOT [red]
#   1) данные: на 7 уровнях у трафика и машин миссий найдены перекрашенные куски (красный: CARFLAT_RECOLOR_OLD=1 — ни одного);
#   2) картинка: L1, серый минивэн трафика (minivanA) в заливке (Textures Off) два раза — с прежними и со свежими боковыми файлами; пиксели, что изменились, обязаны стать цветными (насыщенность >= 0.35, и прежняя была ниже на 0.25).
#   Последняя строка PASS / FAIL (красный обязан дать FAIL).
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/mult956_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; RED=0; [ "${2:-}" = red ] && RED=1
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test59tour/PSP/GAME/SHARTEST15}
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
gen() {   # gen ПАПКА [1 — без перекраски]
  local DT=$1; rm -rf $DT; mkdir -p $DT; ( [ "${2:-0}" = 1 ] && export CARFLAT_RECOLOR_OLD=1
  for n in 1 2 3 4 5 6 7; do ( if [ $n = 1 ]; then d=$SET; o=$DT; else d=$SET/l$n; o=$DT/l$n; mkdir -p $o; fi
    python3 $I/tools/car_flat.py $d/traffic.shr --sidecar $o/carflat930.bin >/dev/null 2>&1; python3 $I/tools/car_flat.py $d/msncars-l$n.shr --sidecar $o/carflatm930.bin >/dev/null 2>&1 ) & done; wait ); }
mkdir -p $OUT; gen $OUT/data_old 1; gen $OUT/data_new $RED
python3 -I - $I $OUT/data_new $SET $RED <<'PYEOF'
import sys, os
sys.path.insert(0, sys.argv[1] + '/tools'); import car_flat as C
D, SET, red = sys.argv[2], sys.argv[3], sys.argv[4] == '1'
if red: C.RECOLOR = False
n = tot = 0
for lv in range(1, 8):
    d = SET if lv == 1 else '%s/l%d' % (SET, lv)
    f, tex, models, pieces, _ = C.load_trf(d + '/traffic.shr')
    for m in models:
        for j in range(m['first'], m['first'] + m['n']):
            p = pieces[j]
            if p['tex'] < 0: continue
            r = C.piece_split(f, tex[p['tex']], p)
            if not r: continue
            tot += 1; c2 = C.recolor956(m['name'], p['wheel'], r[2]); n += c2 is not r[2]
print('  перекрашено кусков трафика (7 уровней): %d из %d с заливкой' % (n, tot))
open(D + '/count.txt', 'w').write(str(n))
PYEOF
N=$(cat $OUT/data_new/count.txt)
cat > $OUT/s956.txt <<'EOS'
wait 12
flag cfgdefaults 1
flag repair
wait 4
flag toon 1
wait 4
flag flat912 1
scene G_ON
foot 295.5 166 3.14
wait 22
flag trfgo 3.8
wait 2
flag trfgo 3.8
wait 2
shot g956
EOS
OVL=$OUT/data_old SET=$SET $RUN $OUT/s956.txt m956_old "$EB" 300 >/dev/null 2>&1 &
OVL=$OUT/data_new SET=$SET $RUN $OUT/s956.txt m956_new "$EB" 300 >/dev/null 2>&1 &
wait
python3 -I - $OUT/out_m956_old $OUT/out_m956_new $N <<'PYEOF'
import sys
from PIL import Image
import numpy as np
n = int(sys.argv[3])
def load(d): return np.asarray(Image.open(d + '/g956.png').convert('RGB'), float) / 255
a, b = load(sys.argv[1]), load(sys.argv[2])
def sat(x): mx = x.max(2); mn = x.min(2); return np.where(mx > .01, (mx - mn) / np.maximum(mx, .01), 0)
m = (np.abs(a - b).sum(2) > .12); m[:60] = False   # без строк экрана сверху
k = int(m.sum()); so = float(np.median(sat(a)[m])) if k else 0.; sn = float(np.median(sat(b)[m])) if k else 0.
print('  изменившихся пикселей %d; насыщенность на них: прежние данные %.2f, новые %.2f' % (k, so, sn))
ok = n > 0 and k >= 400 and sn >= .35 and sn - so >= .25
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PYEOF
