#!/bin/bash
# №989 приёмка: блёстки на объектах (гэги, свечения предметов, выключатели) в 2,5 раза прозрачнее. accept60.sh NEW_EBOOT [red]
#   Мера: (1) журнал GQ944: у «стало» большие блёстки гэга (цвет c8f0ff, размер >= 1,5) с прозрачностью не больше 0,45 и их не меньше одной, у «было» (файл bling989old) — 1,00;
#   монетные блики (c8f0ff, размер < 1,5) и огни (0000ff) те же 0,40 / 0,30, что у «было»; (2) кадр: белых точек (все каналы >= 235) в окне блика у «стало» не больше 55 % от «было», у «было» не меньше 400.
#   «red» — красный контроль: «стало» тоже с файлом bling989old -> прозрачность 1,00, точек поровну -> FAIL. Последняя строка PASS / FAIL
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/bling989_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; RED=0; [ "${2:-}" = red ] && RED=1
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
mkdir -p $OUT; rm -rf $OUT/out_acc_new $OUT/out_acc_old
( [ $RED = 1 ] && export FLAGS=bling989old; $RUN $D/scenario_accept.txt acc_new "$EB" 300 >/dev/null 2>&1 ) &
( FLAGS=bling989old $RUN $D/scenario_accept.txt acc_old "$EB" 300 >/dev/null 2>&1 ) &
wait
python3 -I - "$OUT/out_acc_new" "$OUT/out_acc_old" <<'PYEOF'
import sys, re
from PIL import Image
import numpy as np
dn, do = sys.argv[1], sys.argv[2]
rx = re.compile(r'GQ944 lv=\d+ site=\S+ p=\S+ sc=([\d.]+) abgr=([0-9a-f]+) a=([\d.]+)')
def rd(d):
    try: return [(float(m.group(1)), m.group(2), float(m.group(3))) for m in rx.finditer(open(d + '/smoke.txt', encoding='utf8', errors='replace').read())]
    except OSError: return None
n, o = rd(dn), rd(do)
if n is None or o is None: print('нет smoke.txt'); print('FAIL'); sys.exit(1)
ok_all = True
def chk(ok, s):
    global ok_all; ok_all &= bool(ok); print('  %s %s' % ('ok  ' if ok else 'FAIL', s))
big = lambda L: [a for sc, c, a in L if c == 'c8f0ff' and sc >= 1.5]
coin = lambda L: sorted({a for sc, c, a in L if c == 'c8f0ff' and sc < 1.5}); lamp = lambda L: sorted({a for sc, c, a in L if c == '0000ff'})
chk(len(big(n)) >= 1 and max(big(n)) <= .45, 'блёстки гэга «стало»: %d шт., прозрачность до %.2f (нужно <= 0,45)' % (len(big(n)), max(big(n), default=0)))
chk(len(big(o)) >= 1 and min(big(o)) >= .95, 'блёстки гэга «было»: %d шт., от %.2f (нужно 1,00)' % (len(big(o)), min(big(o), default=0)))
chk(coin(n) == coin(o) and lamp(n) == lamp(o), 'монеты %s и огни %s не изменились (было %s, %s)' % (coin(n), lamp(n), coin(o), lamp(o)))
def wh(d):
    a = np.asarray(Image.open(d + '/A_L6_G1.bmp').convert('RGB'), int)[80:260, 100:380]; return int((a.min(axis=2) >= 235).sum())
try: wn, wo = wh(dn), wh(do)
except OSError: print('нет кадра'); print('FAIL'); sys.exit(1)
chk(wo >= 400 and wn <= .55 * wo, 'белых точек в окне блика: было %d, стало %d (нужно стало <= 55 %% от было, было >= 400)' % (wo, wn))
print('PASS' if ok_all else 'FAIL'); sys.exit(0 if ok_all else 1)
PYEOF
