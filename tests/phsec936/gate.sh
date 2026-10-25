#!/bin/bash
# №936 п.2 гейт: PHSEC/PHSUB считают ВСЕ кадры (smoke.h, SMK_SETTLE936_OLD / «flag smksettle936»). До правки кадры «устаивания» (после телепорта, паузы, загрузки) копились в фазах, а счётчик кадров их не видел:
#   первая строка PHSEC после телепорта/выхода из паузы показывала ×15–25 по всем полям (TEST58 железо: F_SET +19,6 с x_props 114, F_FLAT_L1S +4,7 с x_props 44 при work 26–31). Мера: сумма n по строкам PHSEC / сумма кадров по секундным строкам (fps).
#   gate.sh NEW_EBOOT [MODE]    — MODE 1 (по умолчанию): отношение ≥ 0,88 в новом и < 0,8 в прежнем (flag 0) -> PASS; MODE 0 — красный контроль (оба прежние) -> FAIL
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/phsec936; W=${W:-$ROOT/build/gates/g936}; export OUT=$W; NEW=$1; MODE=${2:-1}
rm -rf $W; mkdir -p $W; sed "s/MODE/0/" $T/pts_L1.txt > $W/o.txt; sed "s/MODE/$MODE/" $T/pts_L1.txt > $W/n.txt
for k in o n; do $RUN $W/$k.txt g936$k $NEW 900 >/dev/null & done; wait
for k in o n; do mv $W/out_g936$k $W/$k; done
python3 - $W <<'PYEOF'
import re, sys
W = sys.argv[1]
def ratio(d):
    n = 0; fr = 0.0; started = 0
    for l in open('%s/%s/smoke.txt' % (W, d), errors='replace'):
        if l.startswith('SCENE P026'): started = 1
        if not started: continue
        if l.startswith('PHSEC'): n += int(re.search(r' n=(\d+)', l).group(1))
        m = re.match(r'(\d+\.\d) (\S+) ([\d.]+) ', l)
        if m: fr += float(m.group(3))
    return n / fr if fr else None
ro, rn = ratio('o'), ratio('n')
if ro is None or rn is None: print('нет строк'); print('FAIL'); sys.exit(1)
print('  кадров в PHSEC / кадров по секундным строкам: прежнее %.2f, новое %.2f' % (ro, rn))
good = rn >= .88 and ro < .8
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
