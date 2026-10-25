#!/bin/bash
# №919 гейт: повтор отсечения города при езде (main_render.h, CR_MOVE_OLD / «flag crmove»): с широкими допусками повтор срабатывает в разы чаще, а каждый повторённый список содержит всё,
#   что видно по свежему отсечению для той же позы (flag crchk 1: строка CRCHK, viol = кусков свежего списка, которых нет в повторённом).
#   gate.sh NEW_EBOOT [MODE]    — MODE 1 (по умолчанию): езда на L4 тура (автопилот, 223 м): viol = 0 и повторов в ≥ 5 раз больше, чем при MODE 0 (допуски B8);
#                                  MODE 2 — красный контроль (широкие допуски без запаса ящиков) -> viol > 0 -> FAIL
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/cullreuse919; W=${W:-$ROOT/build/gates/g919}; export OUT=$W; NEW=$1; MODE=${2:-1}
rm -rf $W; mkdir -p $W; sed "s/MODE/$MODE/" $T/l4.txt > $W/new.txt; sed "s/MODE/0/" $T/l4.txt > $W/old.txt
$RUN $W/new.txt g919n $NEW 1200 >/dev/null & $RUN $W/old.txt g919o $NEW 1200 >/dev/null & wait
mv $W/out_g919n $W/n; mv $W/out_g919o $W/o
python3 - $W $MODE <<'PYEOF'
import re, sys
W, mode = sys.argv[1], sys.argv[2]
def last(d):
    r = ''
    for l in open(W + '/' + d + '/smoke.txt', errors='replace'):
        if l.startswith('CRCHK'): r = l.strip()
    m = re.search(r'mode=(\d+) frames=(\d+) viol=(\d+) cand=(\d+) extra=(\d+)', r)
    return tuple(map(int, m.groups())) if m else None
n, o = last('n'), last('o')
if not n or not o: print('нет строки CRCHK'); print('FAIL'); sys.exit(1)
print('  новое  (mode %d): повторов проверено %d, расхождений %d, кусков в свежих списках %d, лишних в повторённых %d' % n)
print('  прежнее (mode %d): повторов проверено %d, расхождений %d' % (o[0], o[1], o[2]))
good = n[1] >= 5 * max(o[1], 1) and n[2] == 0
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
