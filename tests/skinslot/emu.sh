#!/bin/bash
# №914 гейт в эмуляторе: пешеходы L5 — слов GE на кадр (ped_words в PHSUB) у новых слотов не больше 80 % от прежних (файл skinslotold рядом с EBOOT), картинка «стоя» та же (<= 200 px вне шапки).
#   emu.sh NEW_EBOOT          красный контроль: emu.sh NEW_EBOOT same (оба прогона с файлом skinslotold) -> FAIL (слов не меньше)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/skinslot; W=${W:-$ROOT/build/gates/g914}; export OUT=$W; NEW=$1
rm -rf $W; mkdir -p $W; : > $W/skinslotold
if [ "$2" = same ]; then FLAGS=skinslotold $RUN $T/l5.txt g914n $NEW 600 >/dev/null; else $RUN $T/l5.txt g914n $NEW 600 >/dev/null; fi
FLAGS=skinslotold $RUN $T/l5.txt g914o $NEW 600 >/dev/null; mv $W/out_g914n $W/n; mv $W/out_g914o $W/o
python3 - $W <<'PYEOF'
import re, sys, statistics as st
from PIL import Image
import numpy as np
W = sys.argv[1]
def words(d):
    v = []; scene_t = {}
    for l in open(d + '/smoke.txt', errors='replace'):
        if l.startswith('SCENE '): q = l.split(); scene_t[q[1]] = float(q[2])
        if l.startswith('PHSUB') and 'scene=S5_STAND' in l:
            m = re.search(r'trf_n=[\d.]+/[\d.]+/([\d.]+) .*?ped_words=(\d+)', l)
            if m and float(m.group(1)) >= 1: v.append(float(m.group(2)) / float(m.group(1)))
    return st.median(v) if v else 0.0
wn, wo = words(W + '/n'), words(W + '/o')
a = np.asarray(Image.open(W + '/n/stand.png').convert('RGB'), int)[70:]; b = np.asarray(Image.open(W + '/o/stand.png').convert('RGB'), int)[70:]
px = int((np.abs(a - b).sum(2) > 40).sum())
print('  слов GE на пешехода: новые слоты %.0f, прежние %.0f (%.0f %%); картинка стоя: различие %d px' % (wn, wo, 100 * wn / max(wo, 1), px))
ok1 = wo > 0 and wn <= 0.8 * wo; ok2 = px <= 200
print('%s слов не больше 80 %%' % ('OK' if ok1 else 'КРАСНОЕ')); print('%s картинка та же' % ('OK' if ok2 else 'КРАСНОЕ')); print('PASS' if ok1 and ok2 else 'FAIL'); sys.exit(0 if ok1 and ok2 else 1)
PYEOF
