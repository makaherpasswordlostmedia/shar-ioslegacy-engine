#!/bin/bash
# №951 приёмка: строка Ink переключает перо контура. accept60.sh NEW_EBOOT [OLD_EBOOT]
#   NEW — сборка с №951: стили 0/1/2 дают нужные цвета (INK951 в smoke.txt), на снимках стиль 1 без фиолетового отлива у тёмных пикселей, стиль 0 — с ним.
#   OLD_EBOOT (сборка с -DINK951_OLD=1) — красный контроль: тот же сценарий, стиль 1 всё ещё фиолетовый -> проверка обязана дать FAIL.
# Последняя строка PASS / FAIL. RUN=<дерево>/tools/emu_run.sh, OUT — рабочая папка
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-/tmp/ink951_out}; export EMU_OWNER=${EMU_OWNER:-Мультик}; export EMU_MINE=${EMU_MINE:-2}
EB=$1; MODE=${2:-new}; N=ink951_$MODE
[ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
$RUN $D/scenario.txt $N "$EB" 400 >/dev/null 2>&1
python3 -I - "$OUT/out_$N" "$MODE" <<'PYEOF'
import re, sys, glob, os
from PIL import Image
d, mode = sys.argv[1], sys.argv[2]
log = open(d + '/smoke.txt', errors='replace').read() if os.path.exists(d + '/smoke.txt') else ''
rows = {int(m.group(1)): dict(re.findall(r'(\w+)=(\S+)', m.group(0))) for m in re.finditer(r'INK951 style=(\d)[^\n]*', log)}
ok = True
def need(c, msg):
    global ok
    print(('  ok   ' if c else '  FAIL ') + msg); ok = ok and c
need(set(rows) >= {0, 1, 2}, 'строки INK951 для стилей 0,1,2: %s' % sorted(rows))
def hexv(s, k): return int(rows[s][k], 16) & 0xffffff
def violet(c): r, g, b = c & 255, c >> 8 & 255, c >> 16 & 255; return b - max(r, g) >= 12
if mode == 'new' and set(rows) >= {0, 1, 2}:
    need(all(violet(hexv(0, k)) for k in ('char', 'world')), 'стиль 0: перо героя и мира фиолетовое (как было)')
    need(not any(violet(hexv(1, k)) or hexv(1, k) & 255 > 24 for k in ('char', 'world', 'road', 'prop', 'shadow')), 'стиль 1: все пять перьев чёрные, без фиолетового')
    need(hexv(2, 'char') == hexv(1, 'char') and hexv(2, 'shadow') == hexv(1, 'shadow'), 'стиль 2: герои и тени чёрные')
    need(len({hexv(2, 'world'), hexv(2, 'road'), hexv(2, 'char')}) == 3, 'стиль 2: мир, асфальт и герои — три разных пера')
def violet_share(png):
    im = Image.open(png).convert('RGB'); px = list(im.getdata()); n = v = 0
    for r, g, b in px:
        if max(r, g, b) < 50:   # тушь и тени; пороги: перо индиго #16052C после дымки ещё читается как фиолетовое, ниже 30 — только чёрное
            n += 1; v += (b - max(r, g) >= 10)
    return v / max(n, 1), n
shots = {}
for s in (0, 1):
    for w in ('foot', 'car'):
        p = glob.glob('%s/ink%d_%s*.png' % (d, s, w))
        if p: shots[(s, w)] = violet_share(p[0])
for w in ('foot', 'car'):
    if (0, w) in shots and (1, w) in shots:
        a, b = shots[(0, w)][0], shots[(1, w)][0]
        print('  снимок %s: доля фиолетовых среди тёмных пикселей: стиль 0 %.3f, стиль 1 %.3f' % (w, a, b))
        need(b < a * 0.5, 'снимок %s: у стиля 1 фиолетового отлива вдвое меньше, чем у стиля 0' % w)
    else: need(False, 'нет снимков %s' % w)
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PYEOF
