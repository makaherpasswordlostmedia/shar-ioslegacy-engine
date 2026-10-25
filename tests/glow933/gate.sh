#!/bin/bash
# №933 п.5 гейт: свет ПРОПОВ в таблице света (spritelight.h slLightProps, SLPROPS933_OLD / «flag slprops933»). На L7 у пропов 74 экземпляра малых кусков со сложением (tex 419): NEON_SKIP их не рисует, а таблица света брала
#   только стейтпропы и город — свечения не было. С правкой они попадают в таблицу (строка SLPROPS entries=N) и рисуются одним вызовом вместе со всем светом.
#   gate.sh NEW_EBOOT [MODE]    — MODE 2 (по умолчанию; 1 — плашка, 0 — как было, d — без строки flag: что даёт сама сборка; красный контроль сборки -DSLPROPS933_OLD=1 + MODE d): записей таблицы от пропов >= 20 в новом и 0 в прежнем (flag 0) -> PASS; MODE 0 — красный контроль (оба прежние) -> FAIL
#   OUT (рабочая папка, по умолчанию tests/glow933/out); EMU_OWNER; прогоны через tools/emu_run.sh (общий предел эмуляторов на Мак)
T=$(cd "$(dirname "$0")" && pwd); I=$T/../..; RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-$T/out} EMU_OWNER=${EMU_OWNER:-geocam}; NEW=$1; MODE=${2:-2}
mkdir -p $OUT; rm -rf $OUT/out_g933o $OUT/out_g933n; sed "s/MODE/0/" $T/props_L7.txt > $OUT/o.txt; if [ "$MODE" = d ]; then grep -v "slprops933" $T/props_L7.txt > $OUT/n.txt; else sed "s/MODE/$MODE/" $T/props_L7.txt > $OUT/n.txt; fi
for k in o n; do bash $RUN $OUT/$k.txt g933$k $NEW 900 >/dev/null & done; wait
python3 - $OUT <<'PYEOF'
import re, sys
W = sys.argv[1]
def entries(d):
    t = 0
    try: f = open('%s/out_g933%s/smoke.txt' % (W, d), errors='replace')
    except OSError: return -1
    for l in f:
        m = re.match(r'SLPROPS pieces=(\d+) entries=(\d+)', l)
        if m: t += int(m.group(2))
    return t
o, n = entries('o'), entries('n')
print('  записей таблицы света от пропов L7: прежнее %d, новое %d' % (o, n))
# кадр должен посветлеть: (посветлевших минус потемневших пикселей, порог 30 по сумме каналов) в восьми снимках; красный контроль даёт ~150 (шум), зелёный ~1500 (свечение реально нарисовано, а не только лежит в таблице)
try:
    from PIL import Image
    import numpy as np
    dp = 0
    for nm in ['l0_a','l0_b','l1_a','l1_b','l2_a','l2_b','l3_a','l3_b']:
        a = np.asarray(Image.open('%s/out_g933o/%s.png' % (W, nm)).convert('RGB')).astype(int); b = np.asarray(Image.open('%s/out_g933n/%s.png' % (W, nm)).convert('RGB')).astype(int)
        d_ = (b - a).sum(2); dp += int((d_ > 30).sum()) - int((d_ < -30).sum())   # свет только добавляет яркость: темнеющие пиксели — шум прогона (анимация), вычитаем
except Exception as ex: dp = -1; print('  кадры не сверены:', ex)
print('  пикселей кадра посветлело за вычетом шума (8 снимков): %d' % dp)
for d_, nm in (('o', 'прежнее'), ('n', 'новое')):
    for l in open('%s/out_g933%s/smoke.txt' % (W, d_), errors='replace'):
        m = re.match(r'LIGHTSPR scene=(L\d) .*quads=([\d.]+) draws=([\d.]+) us=(\d+)', l)
        if m and m.group(1) in ('L0', 'L2'): print('  свет %s %s: квадов %s, вызовов %s, %s мкс на кадр (Мак, ×5,8 = PSP)' % (nm, m.group(1), m.group(2), m.group(3), m.group(4)))
good = o == 0 and n >= 20 and dp >= 600
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
