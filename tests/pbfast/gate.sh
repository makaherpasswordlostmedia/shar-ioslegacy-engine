#!/bin/bash
# №915 гейт: запечённые листы пропов (propbake.h, PB_FAST_OLD): скан по списку ближних + срезу, обход активных клеток, базовый динамический список — дают те же списки, что полные обходы.
#   gate.sh NEW_EBOOT [MODE]    — MODE 1 (по умолчанию): PBCHK (сверка списков каждый кадр, flag pbchk 1) dyn_bad=0 и vis_bad=0 на L5 (езда, стоя) и на сцене «камера вплотную к мелким пропам»
#                                  (там клетки идут прежним путём: force_cells > 0, проверяется слияние членов); MODE 2 — красный контроль (база динамических без каждого второго) -> FAIL
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/pbfast; W=${W:-$ROOT/build/gates/g915}; export OUT=$W; NEW=$1; MODE=${2:-1}
rm -rf $W; mkdir -p $W; sed "s/MODE/$MODE/" $T/near.txt > $W/near.txt; sed "s/MODE/$MODE/" $T/l5.txt > $W/l5.txt
$RUN $W/near.txt g915a $NEW 600 >/dev/null; $RUN $W/l5.txt g915b $NEW 600 >/dev/null; mv $W/out_g915a $W/a; mv $W/out_g915b $W/b
python3 - $W <<'PYEOF'
import re, sys
W = sys.argv[1]; ok = True
for d, nm in (('a', 'камера у пропов'), ('b', 'L5 езда')):
    last = ''
    for l in open(W + '/' + d + '/smoke.txt', errors='replace'):
        if l.startswith('PBCHK'): last = l.strip()
    m = re.search(r'frames=(\d+) dyn_bad=(\d+) vis_bad=(\d+) force_cells=(\d+)', last)
    if not m: print('  %s: нет строки PBCHK' % nm); ok = False; continue
    fr, db, vb, fc = map(int, m.groups()); print('  %s: кадров %d, расхождений динамического списка %d, видимых клеток %d, клеток прежним путём %d' % (nm, fr, db, vb, fc))
    good = fr > 1000 and db == 0 and vb == 0 and (d != 'a' or fc > 0)
    print('%s %s' % ('OK' if good else 'КРАСНОЕ', nm)); ok = ok and good
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PYEOF
