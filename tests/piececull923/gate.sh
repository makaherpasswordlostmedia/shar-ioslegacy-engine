#!/bin/bash
# №923 гейт: отсечение кусков крупных пропов и стейтпропов по кадру (main_render.h pcOut923, PIECECULL923_OLD / «flag piececull923»). Точки L1 P061 и P063 (деревья у дороги: 63 куска на 81 суставе, ≈340 вызовов props на кадр).
#   Три прогона одного EBOOT: flag 0 (как было), MODE (по умолчанию 1), сверка (3, а при красном контроле MODE=4 — тот же MODE). В сверке каждый отсечённый кусок проверяется по всем вершинам:
#   вершина внутри всех четырёх плоскостей кадра = нарушение (viol в строке SPTOP).
#   gate.sh NEW_EBOOT [MODE]    — MODE 1: viol = 0, вызовов props на кадр в новом ≤ 0,6 от прежнего, отсечено ≥ 50 % проверенных -> PASS; MODE 4 (радиус ×0,3) — красный контроль: viol > 0 -> FAIL
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; . "$ROOT/tools/gate_env.sh"; T=$ROOT/tests/piececull923; W=${W:-$ROOT/build/gates/g923}; export OUT=$W   # RUN — общий tools/emu_run.sh (СЦЕНАРИЙ МЕТКА EBOOT МАКС_СЕК); свой tests/piececull923/run.sh — только если RUN=… задан явно
NEW=$1; MODE=${2:-1}; CHK=3; [ "$MODE" = 4 ] && CHK=4; [ -f "$NEW" ] || { echo "gate.sh: нет EBOOT $NEW"; exit 2; }
rm -rf $W; mkdir -p $W
sed "s/MODE/0/" $T/pts_L1.txt > $W/o.txt; sed "s/MODE/$MODE/" $T/pts_L1.txt > $W/n.txt; sed "s/MODE/$CHK/" $T/pts_L1.txt > $W/c.txt
for k in o n c; do $RUN $W/$k.txt g923$k $NEW 900 >/dev/null & done; wait
for k in o n c; do mv $W/out_g923$k $W/$k; done
python3 - $W <<'PYEOF'
import re, sys, statistics
W = sys.argv[1]
def calls(d):
    cur = None; v = []
    for l in open('%s/%s/smoke.txt' % (W, d), errors='replace'):
        if l.startswith('SCENE '): cur = l.split()[1]
        if cur and cur.startswith('P') and l.startswith('PHDRAW'):
            m = re.search(r'props=(\d+)/', l); v.append(int(m.group(1)))
    return statistics.median(v[1:]) if len(v) > 1 else None
def sptop(d):
    t = c = viol = 0.0; seen = 0
    for l in open('%s/%s/smoke.txt' % (W, d), errors='replace'):
        m = re.search(r'pcull=([\d.]+)/([\d.]+) viol=(\d+)', l)
        if m: seen += 1; t += float(m.group(1)); c += float(m.group(2)); viol += int(m.group(3))
    return seen, t, c, viol
co, cn = calls('o'), calls('n'); s, t, c, viol = sptop('c'); sn, tn, cnn, _ = sptop('n')
if not co or not cn or not s: print('нет строк PHDRAW/SPTOP (сборка без №923)'); print('FAIL'); sys.exit(1)
print('  вызовов props на кадр (медиана): прежнее %d, новое %d; отсечено кусков %.0f %% проверенных; расхождений при сверке по вершинам: %d' % (co, cn, 100 * cnn / max(tn, 1), viol))
good = viol == 0 and cn <= .6 * co and cnn >= .5 * tn
print('PASS' if good else 'FAIL'); sys.exit(0 if good else 1)
PYEOF
