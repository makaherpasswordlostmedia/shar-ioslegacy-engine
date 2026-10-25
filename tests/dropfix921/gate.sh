#!/bin/bash
# №921 гейт: выброс треугольников GE у глаза у пропов и света (main_render.h, DROPFIX921_OLD / «flag dropfix921»). Сценарии — точки, где боты 24.10 нашли выброс (L1 P026/P027, L3, L4 P045/P063, L5 P000/P029/P040/P041);
#   в каждом: сперва «flag dropfix921 0» (прежнее), затем «flag dropfix921 MODE». DIAGD (flag diaglog 1) — какие куски GE выбрасывает и нарисована ли заплатка (patch=1): считается выброс кусков пропов/света (ph 13/14, own 0) БЕЗ заплатки.
#   gate.sh NEW_EBOOT [MODE]    — MODE 1 (по умолчанию): в старой половине выброса без заплатки ≥ 50, в новой 0 -> PASS; MODE 0 — красный контроль (обе половины прежние) -> FAIL
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/dropfix921; NEW=$1; MODE=${2:-1}; W=${W:-$ROOT/build/gates/g921m$MODE}; export OUT=$W   # Чистота: общий раннер; №940: L3 в списке
rm -rf $W; mkdir -p $W
for L in 1 3 4 5; do sed "s/MODE/$MODE/" $T/ab_L$L.txt > $W/ab_L$L.txt; $RUN $W/ab_L$L.txt g921m${MODE}_L$L $NEW 900 >/dev/null & done; wait
for L in 1 3 4 5; do rm -rf $W/L$L; mv $W/out_g921m${MODE}_L$L $W/L$L; done
python3 - $W <<'PYEOF'
import re, sys, collections
W = sys.argv[1]; tot = collections.Counter(); seen = 0
for L in (1, 3, 4, 5):
    for l in open('%s/L%d/smoke.txt' % (W, L), errors='replace'):
        if not l.startswith('DIAGD '): continue
        seen += 1; m = dict(re.findall(r'(\w+)=(\S+)', l))
        if m['own'] == '0' and m['ph'] in ('13', '14') and m['patch'] == '0': tot[m['sc'][-1]] += int(m['drops'])
if not seen: print('нет строк DIAGD (сборка без диагностики)'); print('FAIL'); sys.exit(1)
print('  выброс кусков пропов/света без заплатки: прежнее %d, новое %d (L1+L3+L4+L5)' % (tot['o'], tot['n']))
good = tot['o'] >= 50 and tot['n'] == 0
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
