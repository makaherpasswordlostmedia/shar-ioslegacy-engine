#!/bin/bash
# №913 гейт: срез у глаза кусков пропов по иерархии групп (GG_PROPBATCH_OLD): быстрее и тот же срез.
#   gate.sh NEW_EBOOT          — MODE 1 против MODE 0 (полный обход, flag ggpropbatch 0) на L5 (езда мимо большого куска пропа, текстура 63, 628 треугольников)
#   gate.sh NEW_EBOOT 0        — красный контроль: оба прогона в режиме 0 -> время не меньше -> FAIL
# Условия: (1) время среза (cut_us строки GGFORCE) у MODE 1 не больше 1/3 от MODE 0 при сопоставимом числе вызовов; (2) число реально срезанных треугольников
# за сцену (cuts в GGFORCE_P) и число вызовов совпадают с MODE 0 точно; (3) картинка «стоя» не отличается (<= 50 px вне шапки)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/ggprop; W=${W:-$ROOT/build/gates/g913gg}; export OUT=$W
NEW=$1; MODE=${2:-1}; rm -rf $W; mkdir -p $W; sed "s/MODE/$MODE/" $T/l5.txt > $W/n.txt; sed "s/MODE/0/" $T/l5.txt > $W/o.txt
$RUN $W/n.txt g913gn $NEW 600 >/dev/null; $RUN $W/o.txt g913go $NEW 600 >/dev/null; mv $W/out_g913gn $W/n; mv $W/out_g913go $W/o
python3 - $W <<'PYEOF'
import re, sys
from PIL import Image
import numpy as np
W = sys.argv[1]
def stats(d):
    us = n = cuts = 0; calls = 0
    for l in open(d + '/smoke.txt', errors='replace'):
        if l.startswith('GGFORCE t=') and 'scene=S5_DRIVE' in l:
            m = re.search(r'cut_us=(\d+)/(\d+)', l); us += int(m.group(1)); calls += int(m.group(2))
        m = re.match(r'GGFORCE_P .* n=(\d+) cuts=(\d+)', l)
        if m and 'tex=63 ' in l: n += int(m.group(1)); cuts += int(m.group(2))
    return us, calls, n, cuts
un, cn, nn, kn = stats(W + '/n'); uo, co, no, ko = stats(W + '/o')
print('  срез на Маке: MODE новый %d мкс за %d вызовов; полный обход %d мкс за %d вызовов' % (un, cn, uo, co))
pn = kn / max(nn, 1); po = ko / max(no, 1)
print('  срезанных треугольников за сцену: новый %d (за %d вызовов), полный обход %d (за %d)' % (kn, nn, ko, no))
a = np.asarray(Image.open(W + '/n/stand.png').convert('RGB'), int)[70:]; b = np.asarray(Image.open(W + '/o/stand.png').convert('RGB'), int)[70:]
px = int((np.abs(a - b).sum(2) > 40).sum()); print('  картинка стоя: различие %d px' % px)
per_n = un / max(cn, 1); per_o = uo / max(co, 1)
ok1 = cn > 20 and co > 20 and per_n * 3 <= per_o; ok2 = ko > 0 and kn == ko and nn == no; ok3 = px <= 50
for t, o in (('время среза на вызов в 3+ раза меньше', ok1), ('срез тот же (число треугольников)', ok2), ('картинка та же', ok3)): print('%s %s' % ('OK' if o else 'КРАСНОЕ', t))
print('PASS' if ok1 and ok2 and ok3 else 'FAIL'); sys.exit(0 if ok1 and ok2 and ok3 else 1)
PYEOF
