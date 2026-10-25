#!/bin/bash
# №913 гейт: свет (lightsprite.h lspDraw) обходит записи в радиусе дальности света, а не всю таблицу (LSP_NEAR_OLD), и ничего не теряет.
#   gate.sh NEW_EBOOT          — режим 1 (по списку): в смоуке lsp_viol (записи вне списка с ненулевым затуханием) == 0 во всех кадрах, список < 25% таблицы
#   gate.sh NEW_EBOOT 2        — красный контроль «flag lspnear 2» (радиус списка 20 м теряет свет): lsp_viol > 0 -> FAIL
#   gate.sh NEW_EBOOT 0        — прежний полный обход: список = вся таблица (проверка, что счётчик отличает режимы) -> FAIL по условию «список меньше таблицы»
# Сцена: L5, 9 мест у фонарей (152 конуса света), tests/lspnear/l5_light.txt (MODE подставляется)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/lspnear; W=${W:-$ROOT/build/gates/g913}; export OUT=$W
NEW=$1; MODE=${2:-1}; rm -rf $W; mkdir -p $W; sed "s/MODE/$MODE/" $T/l5_light.txt > $W/scn.txt
$RUN $W/scn.txt g913 $NEW 600 >/dev/null; mv $W/out_g913 $W/o
python3 - $W/o/smoke.txt <<'PYEOF'
import re, sys
viol = 0.0; n = 0; rat = []
for l in open(sys.argv[1], errors='replace'):
    if l.startswith('PHSUB') and 'scene=S5_STAND' in l:
        m = re.search(r'lsp_list=([\d.]+)/([\d.]+) lsp_viol=([\d.]+)', l)
        if m: n += 1; rat.append(float(m.group(1)) / max(float(m.group(2)), 1)); viol += float(m.group(3))
mr = sum(rat) / max(n, 1)
print('  строк PHSUB %d, список в среднем %.1f%% таблицы, нарушений (записей вне списка с ненулевым светом) в сумме %.2f' % (n, 100 * mr, viol))
ok = n >= 5 and viol == 0 and mr < 0.25
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PYEOF
