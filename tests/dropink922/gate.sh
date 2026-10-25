#!/bin/bash
# №922 гейт: обводка машин (оболочка куска, tex 0) у глаза не теряет треугольники (main_render.h, DROPINK922_OLD / «flag dropink922»). Точки L3 и L5, где боты нашли машины трафика у глаза;
#   два прогона одного EBOOT с одинаковым временем игры: flag 0 (прежнее) и flag MODE. DIAGS drop_ink — выброшенные GE треугольники обводки без заплатки.
#   gate.sh NEW_EBOOT [MODE]    — MODE 1 (по умолчанию): в прежнем прогоне drop_ink ≥ 3 (на TEST59 замер 4; было ≥ 5 на прежнем наборе), в новом 0 -> PASS; MODE 0 — красный контроль (оба прежние) -> FAIL
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/dropink922; W=${W:-$ROOT/build/gates/g922}; export OUT=$W; NEW=$1; MODE=${2:-1}
rm -rf $W; mkdir -p $W
for L in 3 5; do sed "s/MODE/$MODE/" $T/ink_L$L.txt > $W/n_L$L.txt; sed "s/MODE/0/" $T/ink_L$L.txt > $W/o_L$L.txt
  $RUN $W/n_L$L.txt g922n_L$L $NEW 900 >/dev/null & $RUN $W/o_L$L.txt g922o_L$L $NEW 900 >/dev/null & done; wait
for L in 3 5; do mv $W/out_g922n_L$L $W/n$L; mv $W/out_g922o_L$L $W/o$L; done
python3 - $W <<'PYEOF'
import re, sys
W = sys.argv[1]
def ink(d):
    t = seen = 0
    for L in (3, 5):
        for l in open('%s/%s%d/smoke.txt' % (W, d, L), errors='replace'):
            if l.startswith('DIAGS'):
                seen += 1; m = dict(re.findall(r'(\w+)=(\S+)', l)); t += int(m.get('drop_ink', 0))
    return t, seen
(o, so), (n, sn) = ink('o'), ink('n')
if not so or not sn: print('нет строк DIAGS с drop_ink (сборка без №921/№922)'); print('FAIL'); sys.exit(1)
print('  выброшено треугольников обводки без заплатки: прежнее %d, новое %d (L3+L5)' % (o, n))
good = o >= 3 and n == 0   # порог по замеру на наборе TEST59 (24.10, дважды подряд): прежнее 4 (L3 3 + L5 1), новое 0; раньше было 5 на наборе окна «Геометрия». Красный MODE 0 даёт n = o > 0 -> FAIL при любом пороге
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
